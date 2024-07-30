import mercadopago
import os


public_key = os.environ.get("MERCADO_PAGO_PUBLIC_KEY_RESERVA")
token = os.environ.get("MERCADO_PAGO_TOKEN_RESERVA")

def criar_pagamento(itens_pedido, link, email):
    sdk = mercadopago.SDK(token)

    itens = []
    for item in itens_pedido:
        nome_produto = item.item_estoque.produto.nome
        quantidade = int(item.quantidade)
        preco_unitario = float(item.item_estoque.produto.preco)
        itens.append({"title": nome_produto, "quantity": quantidade, "unit_price": preco_unitario})

    preference_data = {
        "items": itens,
        "auto_return": "all",
        "back_urls": {
            "success": link,
            "pending": link,
            "failure": link
        },
        "payer": {
            "email": email
        }
    }

    resposta = sdk.preference().create(preference_data)
    preference = resposta["response"]
    link_pagamento = preference["init_point"]
    id_pagamento = preference["id"]
    return link_pagamento, id_pagamento
