import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import App from "./App";

// useMissionStatus does a real fetch on mount and, on an unauthenticated/empty response,
// navigates away via window.location.href (see hooks/useMissionStatus.ts) -- mock the hook
// itself rather than the network, so this stays a pure "does the tree mount" smoke test.
vi.mock("./hooks/useMissionStatus", () => ({
  useMissionStatus: () => ({ data: null, loading: true, refresh: vi.fn() }),
}));

describe("App", () => {
  it("mounts without throwing", () => {
    expect(() => render(<App />)).not.toThrow();
  });
});
