from .models import Pedido, ItensPedido, Cliente, Categoria, Tipo


def carrinho(request):
    quant_carrinho = 0
    if request.user.is_authenticated:
        cliente = request.user.cliente
    else:
        if request.COOKIES.get('id_sessao'):
            id_sessao = request.COOKIES.get('id_sessao')
            cliente, criado = Cliente.objects.get_or_create(id_sessao=id_sessao)
        else:
            return {"quant_produtos_carrinho": quant_carrinho}
    pedido, criado = Pedido.objects.get_or_create(cliente=cliente, finalizado=False)
    itens_pedido = ItensPedido.objects.filter(pedido=pedido.id)
    for item in itens_pedido:
        quant_carrinho += item.quantidade
    return {"quant_produtos_carrinho": quant_carrinho}


def categorias_tipos(request):
    categorias_navbar = Categoria.objects.all()
    tipos = Tipo.objects.all()
    return {"categorias_navbar": categorias_navbar, "tipos": tipos}


def faz_parte_equipe(request):
    equipe = False
    if request.user.is_authenticated:
        if request.user.groups.filter(name='Equipe').exists():
            equipe = True
    return {"equipe": equipe}
