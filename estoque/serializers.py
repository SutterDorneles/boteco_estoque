# estoque/serializers.py

from rest_framework import serializers
from .models import (Unidade, Produto, Estoque, VendaDiaria, Movimentacao, 
                     PedidoReposicao, ItemReposicao, Fornecedor, PedidoCompra, 
                     ItemPedidoCompra, Ingrediente)

class UnidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unidade
        fields = "__all__"

class ProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produto
        fields = "__all__"

class EstoqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estoque
        fields = "__all__"

class VendaDiariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendaDiaria
        fields = "__all__"

class MovimentacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movimentacao
        fields = "__all__"

# ✅ Adicione os serializers para os novos modelos
class PedidoReposicaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoReposicao
        fields = "__all__"

class ItemReposicaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemReposicao
        fields = "__all__"

# ... (e os outros serializers que você já tem)