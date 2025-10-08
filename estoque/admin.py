# Mantenha todos os seus imports originais
from django.contrib import admin, messages
from django.db import transaction
from .models import Unidade, Produto, Estoque, VendaDiaria, Movimentacao, Fornecedor, PedidoCompra, ItemPedidoCompra, Ingrediente, PedidoReposicao, ItemReposicao, ContagemEstoque, ItemContagemEstoque 
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect, render
from .forms import ImportarVendasForm
import re
from django.utils import timezone
import math
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import pandas as pd
from django.db.models import F

ESTOQUE_SEGURANCA = 0

# As classes Admin para Unidade, Produto e Estoque não precisam de mudanças
@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "endereco")
    search_fields = ("nome", "endereco")
    
class IngredienteInline(admin.TabularInline):
    """
    Permite adicionar/editar ingredientes diretamente na página do Produto Final.
    """
    model = Ingrediente
    # 'fk_name' diz ao Django qual campo do Ingrediente aponta para o Produto "pai".
    fk_name = 'produto_final'
    # Caixa de busca para selecionar o insumo.
    autocomplete_fields = ['insumo']
    extra = 1    

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "unidade_medida")
    list_filter = ("tipo",) # Adicionamos o filtro por tipo
    search_fields = ("nome",)

    # Organiza os campos na tela de edição
    fieldsets = (
        (None, {
            'fields': ('nome', 'tipo', 'unidade_medida')
        }),
    )

    # Esta função mágica mostra o inline de ingredientes APENAS
    # se o produto que você está editando for do tipo "Produto Final".
    def get_inlines(self, request, obj=None):
        if obj and obj.tipo == 'PRODUTO_FINAL':
            return [IngredienteInline]
        return []
    
@admin.register(Estoque)
class EstoqueAdmin(admin.ModelAdmin):
    list_display = ("unidade", "produto", "quantidade", "estoque_minimo")
    list_filter = ("unidade", "produto__tipo", "produto")
    search_fields = ("unidade__nome", "produto__nome")
    list_editable = ("quantidade", "estoque_minimo")
    change_list_template = "admin/estoque/estoque/change_list_gerar_reposicao.html"
    
    # ✅ A ÚNICA CUSTOMIZAÇÃO: O FILTRO PADRÃO
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Se o usuário clicou em um filtro de tipo de produto na URL,
        # nós não fazemos nada e deixamos o Django trabalhar.
        if 'produto__tipo__exact' in request.GET:
            return qs
        
        # Se não, é a primeira visita, então aplicamos nosso filtro padrão.
        return qs.filter(produto__tipo='INSUMO')    
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'gerar-reposicao/',
                self.admin_site.admin_view(self.gerar_reposicao_view),
                name='gerar_reposicao'
            ),
        ]
        return custom_urls + urls

    def gerar_reposicao_view(self, request):
        # Pega o ID da unidade tanto do GET (primeira vez) quanto do POST (envio do form)
        unidade_id = request.GET.get('unidade_id') or request.POST.get('unidade_id')
        if not unidade_id:
            messages.error(request, "Unidade não especificada.")
            return redirect('admin:estoque_estoque_changelist')

        unidade = Unidade.objects.get(id=unidade_id)
        
        # ✅ LÓGICA DO POST COMPLETA
        if request.method == 'POST':
            with transaction.atomic():
                # Cria o "cabeçalho" do pedido de reposição
                novo_pedido = PedidoReposicao.objects.create(unidade_destino=unidade)
                
                itens_adicionados = 0
                # Itera sobre todos os dados enviados pelo formulário
                for key, value in request.POST.items():
                    # Procura por campos que começam com 'produto_'
                    if key.startswith('produto_'):
                        try:
                            quantidade_str = value.replace(',', '.')
                            quantidade = float(quantidade_str) if quantidade_str else 0
                            
                            if quantidade > 0:
                                produto_id = key.split('_')[1]
                                produto = Produto.objects.get(id=produto_id)
                                justificativa = request.POST.get(f'justificativa_{produto_id}', '')

                                ItemReposicao.objects.create(
                                    pedido_reposicao=novo_pedido,
                                    produto=produto,
                                    quantidade_solicitada=quantidade,
                                    justificativa=justificativa
                                )
                                itens_adicionados += 1
                        except (ValueError, IndexError, Produto.DoesNotExist):
                            continue # Ignora campos inválidos ou com quantidade zerada
                
            if itens_adicionados > 0:
                messages.success(request, f"Pedido de Reposição #{novo_pedido.id} criado com {itens_adicionados} item(ns).")
                # Redireciona para a página de edição do novo pedido
                return redirect('admin:estoque_pedidoreposicao_change', novo_pedido.id)
            else:
                messages.warning(request, "Nenhum item com quantidade maior que zero foi adicionado ao pedido.")
                novo_pedido.delete() # Apaga o pedido vazio que foi criado
                return redirect('admin:estoque_estoque_changelist')

        # Lógica para exibir a página (GET)
        itens_sugeridos = Estoque.objects.filter(
            unidade=unidade, 
            quantidade__lte=F('estoque_minimo')
        ).select_related('produto')
        
        sugestoes = []
        for item in itens_sugeridos:
            # ✅ AQUI ESTÁ A CORREÇÃO FINAL E SIMPLIFICADA NO CÁLCULO
            qtd_necessaria = (item.estoque_minimo - item.quantidade) + ESTOQUE_SEGURANCA
            
            sugestoes.append({
                'produto_id': item.produto.id,
                'produto_nome': item.produto.nome,
                'quantidade_sugerida': math.ceil(qtd_necessaria),
                'estoque_atual': item.quantidade,
                'estoque_minimo': item.estoque_minimo,
            })
        
        # Pega todos os insumos para popular o dropdown de itens extras
        todos_insumos = Produto.objects.filter(tipo='INSUMO').values('id', 'nome')

        context = {
            'title': f"Gerar Pedido de Reposição para {unidade.nome}",
            'unidade': unidade,
            'sugestoes': sugestoes,
            'todos_insumos': list(todos_insumos),
            'opts': self.model._meta,
        }
        return render(request, 'admin/estoque/estoque/gerar_reposicao_form.html', context)
        
# --- NOVOS ADMINS PARA O NOVO FLUXO DE REPOSIÇÃO ---

class ItemReposicaoInline(admin.TabularInline):
    model = ItemReposicao
    autocomplete_fields = ['produto']
    extra = 1

@admin.register(PedidoReposicao)
class PedidoReposicaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'unidade_destino', 'status_colorido', 'data_criacao','link_para_concluir')
    list_filter = ('status', 'unidade_destino')
    date_hierarchy = 'data_criacao'
    inlines = [ItemReposicaoInline]
    
    # ✅ Ação para gerar o novo PDF
    actions = ['gerar_pdf_pedido']
    
    # ✅ VERSÃO FINAL USANDO CLASSES DO TEMA
    @admin.display(description="Status")
    def status_colorido(self, obj):
        if obj.status == 'PENDENTE':
            classe_cor = 'warning'  # Classe para amarelo/laranja
        elif obj.status == 'CONCLUIDO':
            classe_cor = 'success'  # Classe para verde
        elif obj.status == 'CANCELADO':
            classe_cor = 'secondary' # Classe para cinza
        else:
            classe_cor = 'dark'     # Classe para escuro

        # Usamos as classes "badge" e "bg-..." do Bootstrap, que o Jazzmin entende.
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            classe_cor, obj.get_status_display()
        )
        
    # ✅ Lógica para criar a URL do botão
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/concluir/',
                self.admin_site.admin_view(self.concluir_pedido_view),
                name='concluir-pedido-reposicao' # Nome único para a URL
            ),
        ]
        return custom_urls + urls    
    
    # ✅ Função para exibir o botão colorido na lista
    def link_para_concluir(self, obj):
        if obj.status == "PENDENTE":
            url = reverse('admin:concluir-pedido-reposicao', args=[obj.pk])
            return format_html('<a class="button" href="{}" style="background-color: #28a745;">Concluir Pedido</a>', url)
        # Mostra o status com cor para os outros casos
        elif obj.status == "CONCLUIDO":
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', obj.get_status_display())
        else:
            return obj.get_status_display()
    link_para_concluir.short_description = "Ação"    
    
    # ✅ A view que executa a conclusão, chamada pelo botão
    def concluir_pedido_view(self, request, object_id):
        try:
            pedido = self.get_object(request, object_id)
            cozinha_central = Unidade.objects.get(nome="Cozinha Central")
        except Unidade.DoesNotExist:
            messages.error(request, "Erro: A unidade 'Cozinha Central' não foi encontrada.")
            return redirect(reverse("admin:estoque_pedidoreposicao_changelist"))

        if pedido.status == "PENDENTE":
            with transaction.atomic():
                for item in pedido.itens.all():
                    Movimentacao.objects.create(
                        tipo="TRANSFERENCIA",
                        produto=item.produto,
                        quantidade=item.quantidade_solicitada,
                        origem=cozinha_central,
                        destino=pedido.unidade_destino
                    )
                pedido.status = "CONCLUIDO"
                pedido.save()
            messages.success(request, f"Pedido #{pedido.id} concluído e estoque transferido com sucesso!")
        else:
            messages.warning(request, f"Pedido #{pedido.id} já estava com status '{pedido.get_status_display()}'.")
        
        return redirect(reverse("admin:estoque_pedidoreposicao_changelist"))    

    @admin.action(description="Gerar PDF do Pedido de Reposição")
    def gerar_pdf_pedido(self, request, queryset):
        # Pega o primeiro (e idealmente único) pedido selecionado
        if queryset.count() != 1:
            self.message_user(request, "Por favor, selecione apenas UM pedido por vez para gerar o PDF.", messages.ERROR)
            return

        pedido = queryset.first()

        context = {
            'pedido': pedido,
            'data_emissao': timezone.now().strftime('%d/%m/%Y'),
        }

        html_string = render_to_string('pdf/pedido_reposicao_pdf.html', context)
        pdf_file = HTML(string=html_string).write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="pedido_reposicao_#{pedido.id}_{pedido.unidade_destino.nome}.pdf"'
        
        return response   

@admin.register(VendaDiaria)
class VendaDiariaAdmin(admin.ModelAdmin):
    # A configuração inicial da classe permanece a mesma
    list_display = ("unidade", "produto", "quantidade", "data")
    list_filter = ("unidade", "produto", "data")
    date_hierarchy = "data"
    change_list_template = "admin/estoque/vendadiaria/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('importar/', self.admin_site.admin_view(self.importar_vendas_view), name='importar_vendas'),
        ]
        return custom_urls + urls
    
    def importar_vendas_view(self, request):
        if request.method == "POST":
            form = ImportarVendasForm(request.POST, request.FILES)
            if form.is_valid():
                unidade = form.cleaned_data['unidade']
                arquivo = form.cleaned_data['arquivo_xls']
                try:
                    df = pd.read_excel(arquivo)
                except Exception as e:
                    messages.error(request, f"Erro ao ler o arquivo: {e}")
                    return redirect('admin:estoque_vendadiaria_changelist')

                erros = []
                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            item_completo = str(row['ITEM'])
                            if ' - ' in item_completo:
                                item_nome_sujo = item_completo.split(' - ', 1)[1]
                            else:
                                item_nome_sujo = item_completo
                            
                            item_nome_limpo = ' '.join(item_nome_sujo.split()).strip()
                            
                            valor_quantidade = row['TOTAL']
                            
                            if pd.isna(valor_quantidade) or not item_nome_limpo or item_nome_limpo.lower() == 'nan':
                                continue
                            
                            try:
                                # ✅ CORREÇÃO AQUI: Limpeza em duas etapas
                                valor_sem_milhar = str(valor_quantidade).replace('.', '')
                                valor_processado = valor_sem_milhar.replace(',', '.')
                                quantidade = int(math.ceil(float(valor_processado)))
                            except ValueError:
                                continue

                            produto, created = Produto.objects.get_or_create(
                                nome=item_nome_limpo,
                                defaults={'tipo': 'INSUMO'}
                            )
                            if created:
                                messages.info(request, f"Produto '{item_nome_limpo}' não existia e foi cadastrado como Insumo.")

                            VendaDiaria.objects.create(
                                unidade=unidade,
                                produto=produto,
                                quantidade=quantidade,
                                data=timezone.now().date()
                            )
                        except KeyError:
                            continue
                        except Exception as e:
                            erros.append(f"Erro na linha {index + 2}: {e}")
                
                if erros:
                    for erro in erros:
                        messages.warning(request, erro)
                    messages.success(request, "Processamento concluído com erros.")
                else:
                    messages.success(request, "Processamento concluído com sucesso!")
                
                return redirect('admin:estoque_vendadiaria_changelist')
        else:
            form = ImportarVendasForm()
        
        context = {
            "form": form,
            "title": "Importar Relatório de Vendas",
            "opts": self.model._meta,
        }
        return render(request, "admin/estoque/vendadiaria/upload_sales.html", context)


# A classe Admin para Movimentacao não precisa de mudanças
@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "produto", "quantidade", "origem", "destino", "data")
    list_filter = ("tipo", "origem", "destino", "produto")
    search_fields = ("origem__nome", "destino__nome", "produto__nome")
    date_hierarchy = "data"
    
# ✅ ADICIONE ESTAS NOVAS CLASSES NO FINAL DO ARQUIVO

@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("nome", "contato_nome", "telefone")
    search_fields = ("nome", "contato_nome")

class ItemPedidoCompraInline(admin.TabularInline):
    """
    Este é o 'Inline'. Ele permite adicionar e editar os Itens do Pedido
    diretamente na tela do Pedido de Compra.
    """
    model = ItemPedidoCompra
    # 'autocomplete_fields' cria uma caixa de busca para o produto,
    # muito melhor que uma lista com milhares de itens.
    autocomplete_fields = ['produto']
    extra = 1 # Começa com 1 linha extra para adicionar um item.

@admin.register(PedidoCompra)
class PedidoCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'fornecedor', 'status_colorido', 'data_pedido', 'data_recebimento', 'numero_nota_fiscal')
    list_filter = ('status', 'fornecedor')
    date_hierarchy = 'data_pedido'
    inlines = [ItemPedidoCompraInline]
    
    # ✅ Registra a nova ação
    actions = ['receber_pedidos']
    
    # ✅ VERSÃO FINAL USANDO CLASSES DO TEMA
    @admin.display(description="Status")
    def status_colorido(self, obj):
        if obj.status == 'PENDENTE':
            classe_cor = 'warning'
        elif obj.status == 'RECEBIDO':
            classe_cor = 'success'
        elif obj.status == 'CANCELADO':
            classe_cor = 'secondary'
        else:
            classe_cor = 'dark'

        # Usamos as classes "badge" e "bg-..." do Bootstrap, que o Jazzmin entende.
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            classe_cor, obj.get_status_display()
        )

    # ✅ A função que executa a mágica
    @admin.action(description="Confirmar recebimento dos itens")
    def receber_pedidos(self, request, queryset):
        # Primeiro, garante que a unidade "Cozinha Central" existe
        try:
            cozinha_central = Unidade.objects.get(nome="Cozinha Central")
        except Unidade.DoesNotExist:
            self.message_user(request, "Erro: A unidade 'Cozinha Central' não foi encontrada. Crie-a antes de receber um pedido.", messages.ERROR)
            return

        # Garante que todas as operações aconteçam com segurança
        with transaction.atomic():
            # Filtra apenas os pedidos que ainda estão pendentes
            pedidos_pendentes = queryset.filter(status="PENDENTE")
            
            for pedido in pedidos_pendentes:
                # Itera sobre cada item dentro do pedido
                for item in pedido.itens.all():
                    # Para cada item, cria a movimentação de ENTRADA no estoque
                    Movimentacao.objects.create(
                        tipo="ENTRADA",
                        produto=item.produto,
                        quantidade=item.quantidade,
                        origem=None, # A origem é externa (o fornecedor)
                        destino=cozinha_central
                    )
                
                # Após processar todos os itens, atualiza o status do pedido
                pedido.status = "RECEBIDO"
                pedido.data_recebimento = timezone.now()
                pedido.save()

        # Informa ao usuário que a operação foi um sucesso
        if pedidos_pendentes:
            self.message_user(request, f"{pedidos_pendentes.count()} pedido(s) foram marcados como 'Recebido' e o estoque foi atualizado.", messages.SUCCESS)
        else:
            self.message_user(request, "Nenhum pedido pendente foi selecionado.", messages.WARNING)
            

@admin.register(ContagemEstoque)
class ContagemEstoqueAdmin(admin.ModelAdmin):
    list_display = ('id', 'unidade', 'data_contagem', 'responsavel', 'finalizada')
    list_filter = ('unidade', 'finalizada')
    
    # ✅ Declaramos nosso template customizado aqui.
    # Ele será usado tanto para a tela de ADICIONAR quanto para a de ALTERAR.
    change_form_template = 'admin/estoque/contagemestoque/change_form.html'
    
    # ✅ Adicionamos a nova ação aqui
    actions = ['finalizar_e_ajustar_estoque']    
    
    # ✅ A LÓGICA DA NOVA AÇÃO
    @admin.action(description="Finalizar e Ajustar Estoque para contagens selecionadas")
    def finalizar_e_ajustar_estoque(self, request, queryset):
        # Filtra apenas as contagens que ainda não foram finalizadas
        contagens_para_processar = queryset.filter(finalizada=False)
        
        if not contagens_para_processar:
            self.message_user(request, "Nenhuma contagem não finalizada foi selecionada.", messages.WARNING)
            return

        with transaction.atomic():
            for contagem in contagens_para_processar:
                # Itera em cada item dentro da contagem
                for item in contagem.itens.all():
                    diferenca = item.diferenca
                    
                    # Se não há diferença, não faz nada, só continua
                    if diferenca == 0:
                        continue
                    
                    # Se a diferença for POSITIVA (contou mais do que o sistema tinha),
                    # criamos uma movimentação de AJUSTE de ENTRADA.
                    elif diferenca > 0:
                        Movimentacao.objects.create(
                            tipo="AJUSTE",
                            produto=item.produto,
                            quantidade=diferenca,
                            origem=None,
                            destino=contagem.unidade
                        )
                    # Se a diferença for NEGATIVA (contou menos, houve perda/saída não registrada),
                    # criamos uma movimentação de AJUSTE de SAÍDA.
                    else:
                        Movimentacao.objects.create(
                            tipo="AJUSTE",
                            produto=item.produto,
                            quantidade=abs(diferenca), # A quantidade é sempre positiva
                            origem=contagem.unidade,
                            destino=None
                        )
                
                # Após processar todos os itens, marca a contagem como finalizada
                # para evitar que seja processada novamente no futuro.
                contagem.finalizada = True
                contagem.save()
        
        self.message_user(request, f"{contagens_para_processar.count()} contagem(ns) foram finalizadas e o estoque foi ajustado.", messages.SUCCESS)    

    # Esta função é chamada QUANDO a página de edição/criação é carregada
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        contagem = self.get_object(request, object_id)

        # Se a contagem já foi finalizada, não permite mais edições na tabela
        if contagem and contagem.finalizada:
            extra_context['contagem_finalizada'] = True
            return super().change_view(request, object_id, form_url, extra_context=extra_context)

        # Pega todos os produtos que são INSUMOS
        todos_insumos = Produto.objects.filter(tipo='INSUMO').order_by('nome')
        
        itens_para_contagem = []
        for produto in todos_insumos:
            try:
                estoque_atual = Estoque.objects.get(unidade=contagem.unidade, produto=produto)
                qtd_sistema = estoque_atual.quantidade
            except Estoque.DoesNotExist:
                qtd_sistema = 0

            item_contagem_existente = ItemContagemEstoque.objects.filter(contagem=contagem, produto=produto).first()
            qtd_fisica = item_contagem_existente.quantidade_fisica if item_contagem_existente else None

            itens_para_contagem.append({
                'produto_id': produto.id,
                'produto_nome': produto.nome,
                'quantidade_sistema': qtd_sistema,
                'quantidade_fisica': qtd_fisica,
            })
        
        extra_context['itens_para_contagem'] = itens_para_contagem
        
        # Processa o formulário quando o usuário clica em "Salvar Contagem"
        if request.method == 'POST' and '_save_contagem' in request.POST:
            with transaction.atomic():
                for item in itens_para_contagem:
                    produto_id = item['produto_id']
                    quantidade_fisica_str = request.POST.get(f'produto_{produto_id}')
                    
                    if quantidade_fisica_str and quantidade_fisica_str.strip() != '':
                        try:
                            quantidade_fisica = int(float(quantidade_fisica_str.replace(',', '.')))
                            produto = Produto.objects.get(id=produto_id)
                            
                            ItemContagemEstoque.objects.update_or_create(
                                contagem=contagem,
                                produto=produto,
                                defaults={
                                    'quantidade_sistema': item['quantidade_sistema'],
                                    'quantidade_fisica': quantidade_fisica,
                                }
                            )
                        except (ValueError, Produto.DoesNotExist):
                            continue
            
            self.message_user(request, "Contagem salva com sucesso!", messages.SUCCESS)
            return self.response_post_save_change(request, contagem)

        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    # Esta função lida com o SALVAR da tela de ADIÇÃO
    def response_add(self, request, obj, post_url_continue=None):
        # Em vez de redirecionar para a lista, redirecionamos para a tela de ALTERAÇÃO
        # para que o usuário possa preencher a tabela de contagem.
        return redirect(reverse('admin:estoque_contagemestoque_change', args=[obj.pk]))
    