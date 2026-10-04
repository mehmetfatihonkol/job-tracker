import { requestJson } from "./http.js";

const raw = document.getElementById("raw");
const parseButton = document.getElementById("parse-btn");
const parseMeta = document.getElementById("parse-meta");
const preview = document.getElementById("preview");
const cards = document.getElementById("cards");
const saveButton = document.getElementById("save-btn");
const saveMeta = document.getElementById("save-meta");
const cardTemplate = document.getElementById("job-card-template");
const frequentThreshold = Number(preview.dataset.frequentThreshold);

const normalizeCompany = (name) => name.trim().toLocaleLowerCase("tr");
let previousApplications = new Map();

async function loadCompanyStats() {
  const companies = await requestJson("/api/companies");
  previousApplications = new Map(companies.map((c) => [normalizeCompany(c.company), c]));
}

function updateCompanyNote(card) {
  const note = card.querySelector('[data-slot="company-note"]');
  const stats = previousApplications.get(normalizeCompany(card.querySelector('[name="company"]').value));
  note.hidden = !stats;
  if (!stats) return;
  const frequent = stats.total >= frequentThreshold;
  note.classList.toggle("is-warning", frequent);
  note.textContent =
    `Bu şirkete daha önce ${stats.total} kez başvurdun ` +
    `(${stats.rejected} red, ${stats.waiting} cevap bekliyor).` +
    (frequent ? " Çok sayıda başvuru yaptın." : "");
}

function renderCard(job, index) {
  const card = cardTemplate.content.firstElementChild.cloneNode(true);
  card.querySelector('[data-slot="heading"]').textContent = `İlan ${index + 1}`;
  for (const field of card.querySelectorAll("[name]")) {
    field.value = job[field.name] ?? "";
  }
  card.querySelector('[name="company"]').addEventListener("input", () => updateCompanyNote(card));
  updateCompanyNote(card);
  return card;
}

function readCard(card) {
  const fields = card.querySelectorAll("[name]");
  return Object.fromEntries([...fields].map((field) => [field.name, field.value]));
}

parseButton.addEventListener("click", async () => {
  parseMeta.textContent = "Parse ediliyor…";
  try {
    const [data] = await Promise.all([
      requestJson("/api/parse", { method: "POST", body: { text: raw.value } }),
      loadCompanyStats(),
    ]);
    cards.replaceChildren(...data.jobs.map(renderCard));
    const fallback = data.error ? ` (fallback: ${data.error})` : "";
    parseMeta.textContent = `parser: ${data.parser}${fallback} — ${data.jobs.length} ilan`;
    preview.hidden = data.jobs.length === 0;
  } catch (error) {
    parseMeta.textContent = `Parse başarısız: ${error.message}`;
  }
});

saveButton.addEventListener("click", async () => {
  const items = [...cards.querySelectorAll(".job-card")]
    .filter((card) => card.querySelector('[data-role="include"]').checked)
    .map(readCard)
    .filter((item) => item.title.trim() && item.company.trim());
  if (items.length === 0) {
    saveMeta.textContent = "Kaydedilecek ilan yok (rol ve şirket zorunlu).";
    return;
  }
  try {
    const data = await requestJson("/api/applications/bulk", { method: "POST", body: { items } });
    saveMeta.textContent = `${data.count} başvuru kaydedildi.`;
    window.location.href = "/applications";
  } catch (error) {
    saveMeta.textContent = `Kayıt başarısız: ${error.message}`;
  }
});
