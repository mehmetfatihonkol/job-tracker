export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function describeDetail(detail) {
  if (Array.isArray(detail)) {
    return detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`).join(", ");
  }
  return typeof detail === "string" ? detail : null;
}

export async function requestJson(url, { method = "GET", body } = {}) {
  const response = await fetch(url, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;
  if (!response.ok) {
    throw new ApiError(describeDetail(payload?.detail) ?? response.statusText, response.status);
  }
  return payload;
}
