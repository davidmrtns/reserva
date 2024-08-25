from django.db.models import Max, Min
from django.core.mail import send_mail
from django.http import HttpResponse
import csv
import os


def filtar_produtos(produtos, filtro):
    if filtro:
        if "-" in filtro:
            categoria, tipo = filtro.split("-")
            produtos = produtos.filter(tipo__slug=tipo, categoria__slug=categoria)
        else:
            produtos_filtrados = produtos.filter(categoria__slug=filtro)
            if len(produtos_filtrados) < 1:
                produtos_filtrados = produtos.filter(tipo__slug=filtro)
            produtos = produtos_filtrados
    return produtos


def preco_minimo_maximo(produtos):
    if len(produtos) > 0:
        minimo = round(list(produtos.aggregate(Min("preco")).values())[0], 2)
        maximo = round(list(produtos.aggregate(Max("preco")).values())[0], 2)
    else:
        minimo = 0
        maximo = 0
    return minimo, maximo


def ordenar_produtos(produtos, ordem):
    if ordem == "menor-preco":
        produtos = produtos.order_by("preco")
    elif ordem == "maior-preco":
        produtos = produtos.order_by("-preco")
    elif ordem == "mais-vendido":
        lista_produtos = []
        for produto in produtos:
            lista_produtos.append((produto.total_vendas(), produto))
        lista_produtos = sorted(lista_produtos, reverse=True, key=lambda tupla: tupla[0])
        produtos = [item[1] for item in lista_produtos]
    return produtos


def enviar_email_compra(pedido):
    email = pedido.cliente.email
    assunto = f"Pedido {pedido.codigo_transacao} aprovado"
    corpo = f"""Parabéns, seu pedido foi aprovado!
            \nID do pedido: {pedido.id}
            \nValor total: {pedido.preco_total}"""
    remetente = os.environ.get("EMAIL_HOST_USER_RESERVA")
    send_mail(assunto, corpo, remetente, [email])


def exportar_csv(informacoes):
    colunas = informacoes.model._meta.fields
    nomes_colunas = [coluna.name for coluna in colunas]
    resposta = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    resposta["Content-Disposition"] = 'attachment; filename=export.csv'
    csv_writer = csv.writer(resposta, delimiter=';')
    csv_writer.writerow(nomes_colunas)
    for linha in informacoes.values_list():
        csv_writer.writerow(linha)
    return resposta
