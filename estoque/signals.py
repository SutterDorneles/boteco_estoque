from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import (Movimentacao, Estoque, VendaDiaria, Produto, 
                     PedidoReposicao, ItemReposicao, Ingrediente) # ✅ 'Reposicao' removido
from django.db.models import F

@receiver(post_save, sender=Movimentacao)
def atualizar_estoque_on_movimentacao(sender, instance, created, **kwargs):
    if not created:
        return
    
# ✅ TRAVA DE SEGURANÇA: 
    # Se for AJUSTE (vindo da contagem), o Signal ignora e não altera o estoque.
    if instance.tipo == 'AJUSTE':
        return    

    # Debita da origem (SAIDA ou TRANSFERENCIA)
    if instance.origem:
        # ✅ Garante que o registro de estoque exista antes de atualizar
        estoque_origem, created = Estoque.objects.get_or_create(
            unidade=instance.origem,
            produto=instance.produto
        )
        # ✅ Usa F() para uma atualização atômica e segura
        estoque_origem.quantidade = F('quantidade') - instance.quantidade
        estoque_origem.save()

    # Credita no destino (ENTRADA ou TRANSFERENCIA)
    if instance.destino:
        estoque_destino, created = Estoque.objects.get_or_create(
            unidade=instance.destino,
            produto=instance.produto
        )
        # ✅ Usa F() para uma atualização atômica e segura
        estoque_destino.quantidade = F('quantidade') + instance.quantidade
        estoque_destino.save()

# Esta função com a lógica de Ficha Técnica continua 100% correta
@receiver(post_save, sender=VendaDiaria)
def criar_movimentacao_on_venda(sender, instance, created, **kwargs):
    if not created:
        return
    produto_vendido = instance.produto
    if produto_vendido.tipo == 'PRODUTO_FINAL':
        for ingrediente in produto_vendido.ingredientes.all():
            quantidade_a_baixar = ingrediente.quantidade * instance.quantidade
            Movimentacao.objects.create(
                tipo="SAIDA",
                produto=ingrediente.insumo,
                quantidade=quantidade_a_baixar,
                origem=instance.unidade
            )
    else:
        Movimentacao.objects.create(
            tipo="SAIDA",
            produto=produto_vendido,
            quantidade=instance.quantidade,
            origem=instance.unidade
        )

# A função de estorno com Ficha Técnica também continua 100% correta
@receiver(post_delete, sender=VendaDiaria)
def reverter_movimentacao_on_venda_delete(sender, instance, **kwargs):
    produto_vendido = instance.produto
    if produto_vendido.tipo == 'PRODUTO_FINAL':
        for ingrediente in produto_vendido.ingredientes.all():
            quantidade_a_estornar = ingrediente.quantidade * instance.quantidade
            Movimentacao.objects.create(
                tipo="ENTRADA",
                produto=ingrediente.insumo,
                quantidade=quantidade_a_estornar,
                destino=instance.unidade
            )
    else:
        Movimentacao.objects.create(
            tipo="ENTRADA",
            produto=produto_vendido,
            quantidade=instance.quantidade,
            destino=instance.unidade
        )

@receiver(post_delete, sender=Movimentacao)
def estornar_estoque_ao_excluir_movimentacao(sender, instance, **kwargs):
    """ 
    Se o usuário apagar uma linha na tabela de Movimentações, 
    o estoque volta ao que era antes.
    """
    
    # Se for AJUSTE (vindo da contagem), não faz nada para não estragar a "Verdade Absoluta"
    if instance.tipo == 'AJUSTE':
        return

    # 1. Se apagou uma SAÍDA (tinha origem): Devolve o que saiu para a origem
    if instance.origem:
        estoque_origem, _ = Estoque.objects.get_or_create(
            unidade=instance.origem, 
            produto=instance.produto,
            defaults={'quantidade': 0}
        )
        estoque_origem.quantidade += instance.quantidade
        estoque_origem.save()

    # 2. Se apagou uma ENTRADA (tinha destino): Retira o que entrou do destino
    if instance.destino:
        estoque_destino, _ = Estoque.objects.get_or_create(
            unidade=instance.destino, 
            produto=instance.produto,
            defaults={'quantidade': 0}
        )
        estoque_destino.quantidade -= instance.quantidade
        estoque_destino.save()