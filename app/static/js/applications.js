import { requestJson } from "./http.js";

for (const select of document.querySelectorAll(".status-select")) {
  let committed = select.value;
  select.addEventListener("change", async () => {
    try {
      await requestJson(`/api/applications/${select.dataset.applicationId}`, {
        method: "PATCH",
        body: { status: select.value },
      });
      committed = select.value;
    } catch (error) {
      select.value = committed;
      window.alert(`Durum güncellenemedi: ${error.message}`);
    }
  });
}

for (const form of document.querySelectorAll("form[data-confirm]")) {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
}
