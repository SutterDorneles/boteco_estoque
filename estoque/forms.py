from django import forms
from .models import Unidade # Importe o modelo Unidade

class ImportarVendasForm(forms.Form):
    unidade = forms.ModelChoiceField(
        queryset=Unidade.objects.all(),
        empty_label="Selecione a Unidade",
        label="Unidade"
    )
    arquivo_xls = forms.FileField(label="Relatório de Vendas (XLS/XLSX)")