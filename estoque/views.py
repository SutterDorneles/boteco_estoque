from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
import pandas as pd
import re
import math
from django.utils import timezone

# ✅ 'Reposicao' e 'ReposicaoSerializer' foram removidos dos imports
from .models import (Unidade, Produto, Estoque, VendaDiaria, Movimentacao, 
                     PedidoReposicao, ItemReposicao)
from .serializers import (UnidadeSerializer, ProdutoSerializer, EstoqueSerializer, 
                          VendaDiariaSerializer, MovimentacaoSerializer,
                          PedidoReposicaoSerializer, ItemReposicaoSerializer)

class UnidadeViewSet(viewsets.ModelViewSet):
    queryset = Unidade.objects.all()
    serializer_class = UnidadeSerializer

class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer

class EstoqueViewSet(viewsets.ModelViewSet):
    queryset = Estoque.objects.all()
    serializer_class = EstoqueSerializer

class VendaDiariaViewSet(viewsets.ModelViewSet):
    queryset = VendaDiaria.objects.all()
    serializer_class = VendaDiariaSerializer

    @action(detail=False, methods=['post'])
    def importar_xls(self, request):
        # ... (código da sua função de importar_xls, sem alterações)
        if 'file' not in request.FILES:
            return Response({"error": "Nenhum arquivo enviado."}, status=status.HTTP_400_BAD_REQUEST)
        
        unidade_nome_ou_id = request.data.get('unidade')
        if not unidade_nome_ou_id:
            return Response({"error": "O nome ou ID da 'unidade' deve ser enviado no corpo da requisição."}, status=status.HTTP_400_BAD_REQUEST)

        unidade_limpa = unidade_nome_ou_id.strip()
        try:
            unidade = Unidade.objects.get(pk=unidade_limpa)
        except (Unidade.DoesNotExist, ValueError):
            try:
                unidade = Unidade.objects.get(nome=unidade_limpa)
            except Unidade.DoesNotExist:
                return Response({"error": f"Unidade com nome ou ID '{unidade_limpa}' não encontrada."}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        try:
            df = pd.read_excel(file)
        except Exception as e:
            return Response({"error": f"Erro ao ler o arquivo: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        vendas_criadas = []
        erros = []
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    item_completo = str(row['ITEM'])
                    partes = item_completo.split(' - ', 1)
                    item_nome_sujo = partes[1].strip() if len(partes) > 1 else item_completo.strip()
                    item_nome_limpo = re.sub(r'\s+', ' ', item_nome_sujo).strip()
                    valor_quantidade = row['TOTAL']
                    if pd.isna(valor_quantidade) or item_nome_limpo == '':
                        continue
                    try:
                        valor_processado = str(valor_quantidade).replace(',', '.')
                        quantidade = int(math.ceil(float(valor_processado)))
                    except ValueError:
                        continue
                    produto, created = Produto.objects.get_or_create(nome=item_nome_limpo)
                    if created:
                        vendas_criadas.append(f"Produto '{item_nome_limpo}' foi cadastrado.")
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
            return Response({"status": "Processamento com erros.", "erros": erros, "criadas": vendas_criadas}, status=status.HTTP_200_OK)
        return Response({"status": "Processamento concluído.", "criadas": vendas_criadas}, status=status.HTTP_201_CREATED)

# ✅ A ViewSet do 'Reposicao' antigo foi REMOVIDA
# class ReposicaoViewSet(viewsets.ModelViewSet):
#     ...

class MovimentacaoViewSet(viewsets.ModelViewSet):
    queryset = Movimentacao.objects.all()
    serializer_class = MovimentacaoSerializer

# ✅ Adicionamos as ViewSets para os novos modelos (opcional, mas boa prática)
class PedidoReposicaoViewSet(viewsets.ModelViewSet):
    queryset = PedidoReposicao.objects.all()
    serializer_class = PedidoReposicaoSerializer

class ItemReposicaoViewSet(viewsets.ModelViewSet):
    queryset = ItemReposicao.objects.all()
    serializer_class = ItemReposicaoSerializer