import { requestJson } from "./http.js";

const form = document.getElementById("detail-form");
const message = document.getElementById("save-msg");
const rejectedField = document.getElementById("rejected-at-field");
const { status, rejected_at: rejectedAt } = form.elements;

function showMessage(text) {
  message.hidden = false;
  message.textContent = text;
}

status.addEventListener("change", () => {
  rejectedField.hidden = status.value !== "rejected";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const updated = await requestJson(`/api/applications/${form.dataset.applicationId}`, {
      method: "PATCH",
      body: Object.fromEntries(new FormData(form)),
    });
    rejectedAt.value = updated.rejected_at ?? "";
    showMessage("Kaydedildi.");
  } catch (error) {
    showMessage(`Kayıt başarısız: ${error.message}`);
  }
});
