var url = new URL(document.URL);
var itens = Array.from(document.getElementsByClassName("item-ordenar"));

itens.map((item) => {
    url.searchParams.set("ordem", item.value);
    item.value = url.href;
});
