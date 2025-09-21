from django.db import models
from django.utils import timezone

class Unidade(models.Model):
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return self.nome

class Produto(models.Model):
    TIPO_CHOICES = [
        ('INSUMO', 'Insumo'), # Itens de estoque (ex: Batata Congelada, Chopp Litro)
        ('PRODUTO_FINAL', 'Produto Final'), # Itens de venda (ex: Porção de Fritas, Torre de Chopp)
    ]
    
    nome = models.CharField(max_length=100)
    unidade_medida = models.CharField(max_length=20, default="unidade")
    # Novo campo para classificar o produto
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='INSUMO')
    
    def __str__(self):
        return self.nome

class Estoque(models.Model):
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.FloatField(default=0)
    estoque_minimo = models.FloatField(default=0) # Adicionado para controle de reposição
    
    class Meta:
        unique_together = ("unidade", "produto")
    
    def __str__(self):
        return f"{self.unidade} - {self.produto} ({self.quantidade})"

class VendaDiaria(models.Model):
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    data = models.DateField(default=timezone.now)
    quantidade = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"Venda em {self.unidade.nome} - {self.produto.nome} ({self.quantidade})"

"""
class Reposicao(models.Model):
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    quantidade = models.FloatField(default=0) # Mudado para FloatField para consistência
    # ✅ MUDANÇA AQUI: Adicionamos o status 'CANCELADA'
    status = models.CharField(
        max_length=20, 
        default="PENDENTE",
        choices=[
            ("PENDENTE", "Pendente"),
            ("CONCLUIDA", "Concluída"),
            ("CANCELADA", "Cancelada"),
        ]
    )
    
    def __str__(self):
        return f"Reposição para {self.unidade.nome} de {self.produto.nome} ({self.quantidade})"
"""

class Movimentacao(models.Model):
    TIPO_CHOICES = [
        ("ENTRADA", "Entrada"),
        ("SAIDA", "Saída"),
        ("TRANSFERENCIA", "Transferência"),
        ("AJUSTE", "Ajuste de Estoque"),         
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.FloatField()
    origem = models.ForeignKey(Unidade, null=True, blank=True, related_name="movimentacao_origem", on_delete=models.SET_NULL)
    destino = models.ForeignKey(Unidade, null=True, blank=True, related_name="movimentacao_destino", on_delete=models.SET_NULL)
    data = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.tipo} - {self.produto} ({self.quantidade})"
    
# ✅ ADICIONE ESTAS TRÊS NOVAS CLASSES ABAIXO

class Fornecedor(models.Model):
    """Guarda as informações dos fornecedores do boteco."""
    nome = models.CharField(max_length=200, unique=True)
    contato_nome = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nome do Contato")
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nome

class PedidoCompra(models.Model):
    """Representa um pedido de compra feito a um fornecedor."""
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("RECEBIDO", "Recebido"),
        ("CANCELADO", "Cancelado"),
    ]

    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT)
    numero_nota_fiscal = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número da NF-e")
    data_pedido = models.DateTimeField(auto_now_add=True, verbose_name="Data do Pedido")
    data_recebimento = models.DateTimeField(blank=True, null=True, verbose_name="Data de Recebimento")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE")

    def __str__(self):
        return f"Pedido {self.id} - {self.fornecedor.nome}"

class ItemPedidoCompra(models.Model):
    """Representa um item dentro de um Pedido de Compra."""
    pedido = models.ForeignKey(PedidoCompra, related_name="itens", on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    quantidade = models.FloatField()
    # Usamos DecimalField para preços para evitar erros de arredondamento de float.
    preco_custo_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True, 
        verbose_name="Preço de Custo Unitário"
    )

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome} no Pedido {self.pedido.id}"    
    
class Ingrediente(models.Model):
    """ Representa um item da ficha técnica (receita) de um produto final. """
    produto_final = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE, 
        related_name='ingredientes',
        limit_choices_to={'tipo': 'PRODUTO_FINAL'} # Garante que só produtos finais possam ter ingredientes
    )
    insumo = models.ForeignKey(
        Produto, 
        on_delete=models.PROTECT, 
        related_name='usado_em',
        limit_choices_to={'tipo': 'INSUMO'} # Garante que apenas insumos possam ser ingredientes
    )
    quantidade = models.FloatField()

    def __str__(self):
        return f"{self.quantidade} {self.insumo.unidade_medida}(s) de {self.insumo.nome} para fazer {self.produto_final.nome}"    
    
# ✅ ADICIONE ESTES DOIS NOVOS MODELOS

class PedidoReposicao(models.Model):
    """ Representa UM pedido de reposição, que pode conter VÁRIOS itens. """
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("CONCLUIDO", "Concluído"),
        ("CANCELADO", "Cancelado"),
    ]
    unidade_destino = models.ForeignKey(Unidade, on_delete=models.PROTECT, verbose_name="Unidade de Destino")
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE")

    def __str__(self):
        return f"Pedido de Reposição #{self.id} para {self.unidade_destino.nome}"

class ItemReposicao(models.Model):
    """ Representa um item DENTRO de um Pedido de Reposição. """
    pedido_reposicao = models.ForeignKey(PedidoReposicao, related_name="itens", on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, limit_choices_to={'tipo': 'INSUMO'})
    quantidade_solicitada = models.FloatField()
    justificativa = models.CharField(max_length=200, blank=True, null=True, help_text="Ex: Perdas, evento especial, etc.")

    def __str__(self):
        return f"{self.quantidade_solicitada}x {self.produto.nome}"    
    
# ✅ ADICIONE ESTAS DUAS NOVAS CLASSES NO FINAL DO ARQUIVO

class ContagemEstoque(models.Model):
    """ O 'cabeçalho' de um evento de contagem de estoque (balanço/inventário). """
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT)
    data_contagem = models.DateTimeField(default=timezone.now)
    responsavel = models.CharField(max_length=100, help_text="Nome da pessoa que realizou a contagem")
    finalizada = models.BooleanField(default=False, help_text="Marca se os ajustes desta contagem já foram processados")
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Contagem em {self.unidade.nome} - {self.data_contagem.strftime('%d/%m/%Y')}"

class ItemContagemEstoque(models.Model):
    """ Cada linha de produto dentro de uma Contagem de Estoque. """
    contagem = models.ForeignKey(ContagemEstoque, related_name="itens", on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, limit_choices_to={'tipo': 'INSUMO'})
    quantidade_sistema = models.FloatField(help_text="Quantidade que o sistema calculava ter no momento da contagem")
    quantidade_fisica = models.FloatField(help_text="Quantidade que foi contada fisicamente")

    @property
    def diferenca(self):
        return self.quantidade_fisica - self.quantidade_sistema

    def __str__(self):
        return f"Contagem de {self.produto.nome}: {self.quantidade_fisica} (Sistema: {self.quantidade_sistema})"    