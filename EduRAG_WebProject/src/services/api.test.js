import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "./api";

describe("apiRequest", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serializes JSON request bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: "session-1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await apiRequest("/api/sessions", {
      method: "POST",
      body: { title: "新的学习问题" },
    });

    expect(response).toEqual({ session_id: "session-1" });
    expect(fetchMock).toHaveBeenCalledWith("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "新的学习问题" }),
    });
  });

  it("surfaces backend error details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "会话不存在" }),
    }));

    await expect(apiRequest("/api/sessions/missing")).rejects.toThrow(
      "会话不存在",
    );
  });
});
