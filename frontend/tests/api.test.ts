/** api.ts helper fonksiyonları için testler — fetch mock'lu. */
import { api } from "../app/lib/api";

describe("api.j() error extraction", () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  it("throws with detail from JSON error body", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: () => Promise.resolve('{"detail":"Rapor bulunamadi"}'),
    });

    await expect(api.getLatestReport()).rejects.toThrow("Rapor bulunamadi");
  });

  it("throws with status when body is empty", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: () => Promise.resolve(""),
    });

    await expect(api.getStatus()).rejects.toThrow("500");
  });

  it("returns parsed JSON on success", async () => {
    const mockReport = {
      id: 1,
      created_at: "2026-01-01T00:00:00",
      summary: "Test rapor",
      candidates_scanned: 10,
      picks: [],
    };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockReport),
    });

    const result = await api.getLatestReport();
    expect(result.id).toBe(1);
    expect(result.summary).toBe("Test rapor");
  });

  it("getReport parses by id", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: 5, summary: "X", picks: [], candidates_scanned: 3, created_at: "" }),
    });

    const result = await api.getReport(5);
    expect(result.id).toBe(5);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/reports/5"),
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("generate posts with optional exchange", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ started: true, exchange: "BIST" }),
    });

    const result = await api.generate("BIST");
    expect(result.started).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("?exchange=BIST"),
      { method: "POST" },
    );
  });
});
