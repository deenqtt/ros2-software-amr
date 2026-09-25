const WEBSOCKET_PROTOCOLS = new Set(["ws:", "wss:"])

/**
 * Validate the ROS bridge URL supplied through Vite's environment.
 * The original value is preserved so the displayed target matches the
 * configured target exactly.
 */
export function resolveRosConfig(value) {
  const url = typeof value === "string" ? value.trim() : ""

  if (!url) {
    return {
      url: "",
      valid: false,
      error: "VITE_ROS_URL belum dikonfigurasi.",
    }
  }

  try {
    const parsed = new URL(url)
    if (!WEBSOCKET_PROTOCOLS.has(parsed.protocol) || !parsed.hostname) {
      throw new Error("invalid websocket protocol")
    }
  } catch {
    return {
      url,
      valid: false,
      error: "VITE_ROS_URL harus berupa URL WebSocket ws:// atau wss:// yang valid.",
    }
  }

  return { url, valid: true, error: "" }
}
