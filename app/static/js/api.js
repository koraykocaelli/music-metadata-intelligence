// Thin wrapper around the existing REST API. No business logic lives here.

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function cleanMessage(message) {
  return String(message).replace(/^Value error, /, "");
}

export function describeDetail(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => cleanMessage(item.msg)).join(" ");
  }
  return `The server returned an error (HTTP ${status}).`;
}

/**
 * Map FastAPI validation errors to fields.
 * Returns entries like { path: ["tracks", 3, "isrc"], field: "isrc", message }.
 */
export function validationErrors(error) {
  if (!(error instanceof ApiError) || !Array.isArray(error.detail)) return [];
  return error.detail.map((item) => {
    const path = (item.loc || []).filter((part) => part !== "body");
    return {
      path,
      field: path.length ? String(path[path.length - 1]) : null,
      message: cleanMessage(item.msg),
    };
  });
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (networkError) {
    throw new ApiError("Could not reach the server. Check that the application is running.", 0, null);
  }

  if (!response.ok) {
    let detail = null;
    try {
      detail = (await response.json()).detail;
    } catch (parseError) {
      // Non-JSON error body; fall back to the status code.
    }
    throw new ApiError(describeDetail(detail, response.status), response.status, detail);
  }

  return response;
}

export async function getJson(path) {
  return (await request(path, { headers: { Accept: "application/json" } })).json();
}

export async function postJson(path, body) {
  const response = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  return response.json();
}

export async function postFile(path, blob, contentType) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": contentType },
    body: blob,
  });
}

export const api = {
  health: () => getJson("/health/database"),
  version: async () => (await getJson("/openapi.json")).info.version,
  listTracks: () => getJson("/api/v1/tracks"),
  createTrack: (track) => postJson("/api/v1/tracks", track),
  matchTrack: (track) => postJson("/api/v1/tracks/similar", track),
  matchBatch: (tracks) => postJson("/api/v1/tracks/batch/match", { tracks }),
};
