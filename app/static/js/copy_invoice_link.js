function copyInvoiceLink() {
  // Формируем ту же ссылку, что и для WhatsApp
  const link = "https://wa.me/{{ inv.phone|replace(' ', '') }}?text=Здравствуйте!%20Ваша%20накладная%20№{{ inv.id }}%20от%20{{ inv.created_at.strftime('%Y-%m-%d') }}%20—%20{{ invoice_url }}";
  
  navigator.clipboard.writeText(link).then(() => {
    alert("Ссылка скопирована в буфер обмена!");
  }).catch(err => {
    console.error("Ошибка при копировании: ", err);
    alert("Не удалось скопировать ссылку 😕");
  });
}
