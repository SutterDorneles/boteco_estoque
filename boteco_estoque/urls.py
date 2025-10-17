from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from django.shortcuts import render
from estoque.models import Unidade, Produto, Movimentacao, Estoque, PedidoReposicao, PedidoCompra, VendaDiaria
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncWeek 

# ✅ 'ReposicaoViewSet' foi removido e as novas ViewSets foram adicionadas
from estoque.views import (
    UnidadeViewSet, ProdutoViewSet, EstoqueViewSet, VendaDiariaViewSet, 
    MovimentacaoViewSet, PedidoReposicaoViewSet, ItemReposicaoViewSet
)

router = routers.DefaultRouter()
router.register(r'unidades', UnidadeViewSet)
router.register(r'produtos', ProdutoViewSet)
router.register(r'estoque', EstoqueViewSet)
router.register(r'vendas', VendaDiariaViewSet)
router.register(r'movimentacoes', MovimentacaoViewSet)
# ✅ A rota do 'ReposicaoViewSet' foi removida
# router.register(r'reposicoes', ReposicaoViewSet) 
# ✅ Adicionamos as novas rotas para a API
router.register(r'pedidos-reposicao', PedidoReposicaoViewSet)
router.register(r'itens-reposicao', ItemReposicaoViewSet)


# ✅ SUBSTITUA SUA FUNÇÃO 'home' POR ESTA VERSÃO
@login_required
def home(request):
    # Lógica do filtro de unidade (continua igual)
    unidade_selecionada_id = request.GET.get('unidade_id')
    
    # ✅ NOVO: Lógica do filtro de tipo de produto
    # Pega o tipo selecionado do URL. Se nada for passado, o padrão é 'INSUMO'.
    tipo_selecionado = request.GET.get('tipo', 'INSUMO')

    # Começa a busca por todos os itens de estoque
    estoque_items = Estoque.objects.select_related('unidade', 'produto').all()

    # Aplica o filtro de unidade, se houver
    if unidade_selecionada_id and unidade_selecionada_id.isdigit():
        estoque_items = estoque_items.filter(unidade_id=unidade_selecionada_id)

    # ✅ NOVO: Aplica o filtro de tipo de produto
    # Se o tipo selecionado não for 'TODOS', filtra pelo tipo.
    if tipo_selecionado != 'TODOS':
        estoque_items = estoque_items.filter(produto__tipo=tipo_selecionado)

    # Ordena o resultado final
    estoque_items = estoque_items.order_by('unidade__nome', 'produto__nome')

    # O resto das buscas para o dashboard continua igual
    reposicoes_pendentes = PedidoReposicao.objects.filter(status="PENDENTE").order_by('data_criacao')
    compras_pendentes = PedidoCompra.objects.filter(status="PENDENTE").order_by('data_pedido')
    todas_unidades = Unidade.objects.all()

    context = {
        "total_produtos": Produto.objects.filter(tipo='INSUMO').count(),
        "total_unidades": Unidade.objects.count(),
        "total_movimentacoes": Movimentacao.objects.count(),
        "reposicoes_pendentes": reposicoes_pendentes,
        "compras_pendentes": compras_pendentes,
        "estoque_items": estoque_items,
        "todas_unidades": todas_unidades,
        "unidade_selecionada_id": unidade_selecionada_id,
        "tipo_selecionado": tipo_selecionado, # ✅ Enviamos o filtro ativo para o template
    }
    return render(request, "home.html", context)


@login_required
def relatorios_view(request):
    # Relatório 1: Top 10 Produtos
    vendas_por_produto = (VendaDiaria.objects
        .values('produto__nome')
        .annotate(total_vendido=Sum('quantidade')).order_by('-total_vendido')[:10])
    top_produtos_labels = [item['produto__nome'] for item in vendas_por_produto]
    top_produtos_data = [item['total_vendido'] for item in vendas_por_produto]

    # Relatório 2: Top Unidades por Vendas
    vendas_por_unidade = (VendaDiaria.objects
        .values('unidade__nome')
        .annotate(total_vendido=Sum('quantidade')).order_by('-total_vendido'))
    top_unidades_labels = [item['unidade__nome'] for item in vendas_por_unidade]
    top_unidades_data = [item['total_vendido'] for item in vendas_por_unidade]

    # Relatório 3: Vendas POR SEMANA
    vendas_por_semana = (VendaDiaria.objects
        .annotate(semana=TruncWeek('data'))
        .values('semana')
        .annotate(total_vendido=Sum('quantidade')).order_by('semana'))

    # ✅ CORREÇÃO AQUI: Removemos o .date() desnecessário
    vendas_semana_labels = [item['semana'].strftime('Semana %d/%m') for item in vendas_por_semana]
    vendas_semana_data = [item['total_vendido'] for item in vendas_por_semana]

    context = {
        'top_produtos_labels': top_produtos_labels,
        'top_produtos_data': top_produtos_data,
        'top_unidades_labels': top_unidades_labels,
        'top_unidades_data': top_unidades_data,
        'vendas_semana_labels': vendas_semana_labels,
        'vendas_semana_data': vendas_semana_data,
    }
    return render(request, "relatorios.html", context)


urlpatterns = [
    path("", home, name="home"),
    path("relatorios/", relatorios_view, name="relatorios"),    
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
]