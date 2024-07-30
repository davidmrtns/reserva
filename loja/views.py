from django.contrib.auth.models import User
from django.urls import reverse
from django.shortcuts import render, redirect
from loja.models import Produto, Banner, ItemEstoque, Cor, Pedido, ItensPedido, Cliente, Endereco, Categoria, Pagamento
import uuid
from .utils import filtar_produtos, preco_minimo_maximo, ordenar_produtos, enviar_email_compra, exportar_csv
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from datetime import datetime
from .api_mercado_pago import criar_pagamento


def homepage(request):
    banners = Banner.objects.filter(ativo=True)
    context = {"banners": banners}
    return render(request, template_name='homepage.html', context=context)


def loja(request, filtro=None):
    produtos = Produto.objects.filter(ativo=True)
    produtos = filtar_produtos(produtos, filtro)

    if request.method == "POST":
        dados = request.POST.dict()
        produtos = produtos.filter(preco__gte=dados.get("preco_minimo"), preco__lte=dados.get("preco_maximo"))
        if "tamanho" in dados:
            itens = ItemEstoque.objects.filter(produto__in=produtos, tamanho=dados.get("tamanho"))
            ids_produtos = itens.values_list('produto', flat=True).distinct()
            produtos = produtos.filter(id__in=ids_produtos)
        if "categoria" in dados:
            produtos = produtos.filter(categoria__slug=dados.get("categoria"))
        if "tipo" in dados:
            produtos = produtos.filter(tipo__slug=dados.get("tipo"))
    itens = ItemEstoque.objects.filter(quantidade__gt=0, produto__in=produtos)
    tamanhos = itens.values_list("tamanho", flat=True).distinct()
    ids_categorias = produtos.values_list("categoria", flat=True).distinct()
    categorias = Categoria.objects.filter(id__in=ids_categorias)
    minimo, maximo = preco_minimo_maximo(produtos)

    ordem = request.GET.get("ordem", "mais-vendido")
    produtos = ordenar_produtos(produtos, ordem)

    context = {"produtos": produtos, "minimo": minimo, "maximo": maximo,
               "tamanhos": tamanhos, "categorias": categorias}
    return render(request, template_name='loja.html', context=context)


def ver_produto(request, id_produto, id_cor=None):
    tem_estoque = False
    cores = {}
    tamanhos = {}
    cor_selecionada = None
    produto = Produto.objects.get(id=id_produto)
    itens_estoque = ItemEstoque.objects.filter(produto=produto, quantidade__gt=0)
    if len(itens_estoque) > 0:
        tem_estoque = True
        cores = {item.cor for item in itens_estoque}
        if id_cor:
            itens_estoque = ItemEstoque.objects.filter(produto=produto, quantidade__gt=0, cor__id=id_cor)
            tamanhos = {item.tamanho for item in itens_estoque}
            cor_selecionada = Cor.objects.get(id=id_cor)
    similares = Produto.objects.filter(categoria__id=produto.categoria.id, tipo__id=produto.tipo.id).exclude(id=produto.id)[:4]
    context = {"produto": produto,"tem_estoque": tem_estoque, "cores": cores, "tamanhos": tamanhos,
               "cor_selecionada": cor_selecionada, "similares": similares}
    return render(request, template_name='ver_produto.html', context=context)


def adicionar_carrinho(request, id_produto):
    if request.method == "POST" and id_produto:
        dados = request.POST.dict()
        tamanho = dados.get("tamanho")
        id_cor = dados.get("cor")
        if not tamanho:
            return redirect('loja')
        resposta = redirect('carrinho')
        if request.user.is_authenticated:
            cliente = request.user.cliente
        else:
            if request.COOKIES.get('id_sessao'):
                id_sessao = request.COOKIES.get('id_sessao')
            else:
                id_sessao = str(uuid.uuid4())
                resposta.set_cookie(key='id_sessao', value=id_sessao, max_age=60*60*24*30)
            cliente, criado = Cliente.objects.get_or_create(id_sessao=id_sessao)
        pedido, criado = Pedido.objects.get_or_create(cliente=cliente, finalizado=False)
        item_estoque = ItemEstoque.objects.get(produto__id=id_produto, tamanho=tamanho, cor__id=id_cor)
        item_pedido, criado = ItensPedido.objects.get_or_create(item_estoque=item_estoque, pedido=pedido)
        item_pedido.quantidade += 1
        item_pedido.save()
        return resposta
    else:
        return redirect('loja')


def remover_carrinho(request, id_produto):
    if request.method == "POST" and id_produto:
        dados = request.POST.dict()
        tamanho = dados.get("tamanho")
        id_cor = dados.get("cor")
        if not tamanho:
            return redirect('loja')
        if request.user.is_authenticated:
            cliente = request.user.cliente
        else:
            if request.COOKIES.get('id_sessao'):
                id_sessao = request.COOKIES.get('id_sessao')
                cliente, criado = Cliente.objects.get_or_create(id_sessao=id_sessao)
            else:
                return redirect('loja')
        pedido, criado = Pedido.objects.get_or_create(cliente=cliente, finalizado=False)
        item_estoque = ItemEstoque.objects.get(produto__id=id_produto, tamanho=tamanho, cor__id=id_cor)
        item_pedido, criado = ItensPedido.objects.get_or_create(item_estoque=item_estoque, pedido=pedido)
        if item_pedido.quantidade <= 1:
            item_pedido.delete()
        else:
            item_pedido.quantidade -= 1
            item_pedido.save()
        return redirect('carrinho')
    else:
        return redirect('loja')


def carrinho(request):
    if request.user.is_authenticated:
        cliente = request.user.cliente
    else:
        if request.COOKIES.get('id_sessao'):
            id_sessao = request.COOKIES.get('id_sessao')
            cliente, criado = Cliente.objects.get_or_create(id_sessao=id_sessao)
        else:
            context = {"cliente_existente": False, "itens_pedido": None, "pedido": None}
            return render(request, template_name='carrinho.html', context=context)
    pedido, criado = Pedido.objects.get_or_create(cliente=cliente, finalizado=False)
    itens_pedido = ItensPedido.objects.filter(pedido=pedido.id)
    context = {"cliente_existente": True, "itens_pedido": itens_pedido, "pedido": pedido}
    return render(request, template_name='carrinho.html', context=context)


def checkout(request):
    if request.user.is_authenticated:
        cliente = request.user.cliente
    else:
        if request.COOKIES.get('id_sessao'):
            id_sessao = request.COOKIES.get('id_sessao')
            cliente, criado = Cliente.objects.get_or_create(id_sessao=id_sessao)
        else:
            return redirect('loja')
    pedido, criado = Pedido.objects.get_or_create(cliente=cliente, finalizado=False)
    enderecos = Endereco.objects.filter(cliente=cliente)
    context = {"pedido": pedido, "enderecos": enderecos, "erro": None}
    if pedido.quantidade_total >= 1:
        return render(request, template_name='checkout.html', context=context)
    else:
        return redirect('carrinho')


def finalizar_pedido(request, id_pedido):
    erro = None
    if request.method == "POST":
        dados = request.POST.dict()
        total = float(dados.get("total").replace(",", "."))
        pedido = Pedido.objects.get(id=id_pedido)
        if total != float(pedido.preco_total):
            erro = "preco"
        if not "endereco" in dados:
            erro = "endereco"
        else:
            endereco = dados.get("endereco")
            pedido.endereco = Endereco.objects.get(id=endereco)
        if not request.user.is_authenticated:
            email = dados.get("email").strip()
            try:
                validate_email(email)
            except ValidationError:
                erro = "email"
            if not erro:
                clientes = Cliente.objects.filter(email=email)
                if clientes:
                    pedido.cliente = clientes[0]
                else:
                    pedido.cliente.email = email
                    pedido.cliente.save()
        else:
            email = request.user.email
        codigo_transacao = f"{pedido.id}-{datetime.now().timestamp()}"
        pedido.codigo_transacao = codigo_transacao
        pedido.save()
        if erro:
            enderecos = Endereco.objects.filter(cliente=pedido.cliente)
            context = {"erro": erro, "pedido": pedido, "enderecos": enderecos}
            return render(request, template_name="checkout.html", context=context)
        else:
            itens_pedido = ItensPedido.objects.filter(pedido=pedido)
            link = request.build_absolute_uri(reverse("finalizar_pagamento"))
            link_pagamento, id_pagamento = criar_pagamento(itens_pedido, link, email)
            pagamento = Pagamento.objects.create(id_pagamento=id_pagamento, pedido=pedido)
            pagamento.save()
            return redirect(link_pagamento)
    else:
        return redirect('loja')


def finalizar_pagamento(request):
    dados = request.GET.dict()
    status = dados.get("status")
    id_pagamento = dados.get("preference_id")
    if status == "approved":
        pagamento = Pagamento.objects.get(id_pagamento=id_pagamento)
        pagamento.aprovado = True
        pedido = pagamento.pedido
        pedido.finalizado = True
        pedido.data_finalizacao = datetime.now()
        pagamento.save()
        pedido.save()
        enviar_email_compra(pedido)
        if request.user.is_authenticated:
            return redirect('meus_pedidos')
        else:
            return redirect('pedido_aprovado', pedido.id)
    else:
        return redirect('checkout')


def pedido_aprovado(request, id_pedido):
    pedido = Pedido.objects.get(id=id_pedido)
    context = {"pedido": pedido}
    return render(request, template_name="pedido_aprovado.html", context=context)


def adicionar_endereco(request):
    if request.method == 'POST':
        if request.user.is_authenticated:
            cliente = request.user.cliente
        else:
            if request.COOKIES.get('id_sessao'):
                id_sessao = request.COOKIES.get('id_sessao')
                cliente, criado = Cliente.objects.get_or_create(id_sessao=id_sessao)
            else:
                return redirect('loja')
        dados = request.POST.dict()
        endereco = Endereco.objects.create(cliente=cliente, rua=dados.get("rua"), numero=int(dados.get("numero")), bairro=dados.get("bairro"),
                                           estado=dados.get("estado"), cidade=dados.get("cidade"), cep=dados.get("cep"))
        endereco.save()
        return redirect('checkout')
    else:
        context = {}
        return render(request, template_name="adicionar_endereco.html", context=context)


def criar_conta(request):
    erro = None
    if request.user.is_authenticated:
        return redirect("loja")
    if request.method == 'POST':
        dados = request.POST.dict()
        if "nome" in dados and "email" in dados and "senha" in dados and "confirmacao_senha" in dados:
            nome = dados.get("nome").strip()
            email = dados.get("email").strip()
            senha = dados.get("senha")
            confirmacao_senha = dados.get("confirmacao_senha")
            try:
                validate_email(email)
            except ValidationError:
                erro = "email_invalido"
            if nome == '':
                erro = "nome_invalido"
            elif senha != confirmacao_senha:
                erro = "senha_diferentes"
            else:
                usuario, criado = User.objects.get_or_create(username=email, email=email)
                if not criado:
                    erro = "usuario_existente"
                else:
                    usuario.set_password(senha)
                    usuario.save()
                    usuario = authenticate(request, username=email, password=senha)
                    login(request, usuario)
                    if request.COOKIES.get('id_sessao'):
                        id_sessao = request.COOKIES.get('id_sessao')
                        cliente, criado = Cliente.objects.get_or_create(id_sessao=id_sessao)
                    else:
                        cliente, criado = Cliente.objects.get_or_create(email=email)
                    cliente.usuario = usuario
                    cliente.nome = nome
                    cliente.email = email
                    cliente.save()
                    return redirect('loja')
        else:
            erro = "preenchimento"
    context = {"erro": erro}
    return render(request, template_name='usuario/criar_conta.html', context=context)


@login_required
def minha_conta(request):
    erro = None
    alterado = False
    if request.method == "POST":
        dados = request.POST.dict()
        if "senha_atual" in dados:
            senha_atual = dados.get("senha_atual")
            nova_senha = dados.get("nova_senha")
            nova_senha_confirmacao = dados.get("nova_senha_confirmacao")
            if nova_senha == nova_senha_confirmacao:
                usuario = authenticate(request, username=request.user.email, password=senha_atual)
                if usuario:
                    usuario.set_password(nova_senha)
                    usuario.save()
                    alterado = True
                else:
                    erro = "senha_incorreta"
            else:
                erro = "senhas_diferentes"
        elif "email" in dados:
            nome = dados.get("nome").strip()
            email = dados.get("email").strip()
            telefone = dados.get("telefone").strip()
            try:
                validate_email(email)
            except ValidationError:
                erro = "formulario_invalido"
            if not erro and nome != "" and telefone != "":
                if email != request.user.email:
                    usuarios = User.objects.filter(email=email)
                    if len(usuarios) > 0:
                        erro = "email_existente"
                if not erro:
                    cliente = request.user.cliente
                    cliente.email = email
                    request.user.email = email
                    request.user.username = email
                    cliente.nome = nome
                    cliente.telefone = telefone
                    cliente.save()
                    request.user.save()
                    alterado = True
            else:
                erro = "formulario_invalido"
        else:
            erro = "formulario_invalido"
    context = {"erro": erro, "alterado": alterado}
    return render(request, template_name='usuario/conta.html', context=context)


@login_required
def meus_pedidos(request):
    cliente = request.user.cliente
    pedidos = Pedido.objects.filter(finalizado=True, cliente=cliente).order_by('-data_finalizacao')
    context = {"pedidos": pedidos}
    return render(request, template_name="usuario/meus_pedidos.html", context=context)


def fazer_login(request):
    erro = False
    if request.user.is_authenticated:
        return redirect('loja')
    if request.method == 'POST':
        dados = request.POST.dict()
        if "email" in dados and "senha" in dados:
            email = dados.get("email")
            senha = dados.get("senha")
            usuario = authenticate(request, username=email, password=senha)
            if usuario:
                login(request, usuario)
                return redirect('loja')
            else:
                erro = True
        else:
            erro = True
    context = {"erro": erro}
    return render(request, template_name='usuario/login.html', context=context)


@login_required
def fazer_logout(request):
    logout(request)
    return redirect('login')


@login_required
def gerenciar_loja(request):
    if request.user.groups.filter(name='Equipe').exists():
        pedidos_finalizados = Pedido.objects.filter(finalizado=True)
        qtd_pedidos = len(pedidos_finalizados)
        qtd_produtos = sum(pedido.quantidade_total for pedido in pedidos_finalizados)
        faturamento = sum(pedido.preco_total for pedido in pedidos_finalizados)
        context = {"qtd_pedidos": qtd_pedidos, "qtd_produtos": qtd_produtos, "faturamento": faturamento}
        return render(request, template_name="interno/gerenciar_loja.html", context=context)
    else:
        redirect('loja')


@login_required
def exportar_relatorio(request, relatorio):
    if request.user.groups.filter(name='Equipe').exists():
        if relatorio == "pedidos":
            informacoes = Pedido.objects.filter(finalizado=True)
        elif relatorio == "clientes":
            informacoes = Cliente.objects.all()
        elif relatorio == "enderecos":
            informacoes = Endereco.objects.all()
        else:
            return redirect('gerenciar_loja')
        return exportar_csv(informacoes)
    else:
        return redirect('loja')
