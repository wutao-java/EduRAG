const configuredApiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(
  /\/$/,
  "",
);

function buildApiUrl(path) {
  return `${configuredApiBaseUrl}${path}`;
}

function buildWebSocketUrl(path) {
  const configuredWebSocketBaseUrl = (
    import.meta.env.VITE_WS_BASE_URL || ""
  ).replace(/\/$/, "");
  if (configuredWebSocketBaseUrl) {
    return `${configuredWebSocketBaseUrl}${path}`;
  }

  const httpUrl = new URL(configuredApiBaseUrl || window.location.origin);
  httpUrl.protocol = httpUrl.protocol === "https:" ? "wss:" : "ws:";
  return new URL(path, httpUrl).toString();
}

export async function apiRequest(path, options = {}) {
  const requestOptions = { ...options };
  if (requestOptions.body && !(requestOptions.body instanceof FormData)) {
    requestOptions.headers = {
      "Content-Type": "application/json",
      ...requestOptions.headers,
    };
    requestOptions.body = JSON.stringify(requestOptions.body);
  }

  const response = await fetch(buildApiUrl(path), requestOptions);
  const responseData = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responseData.detail || "请求失败，请稍后重试");
  }
  return responseData;
}

export function streamAnswer(payload, handlers = {}) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(buildWebSocketUrl("/api/stream"));
    let completed = false;

    socket.addEventListener("open", () => {
      socket.send(JSON.stringify(payload));
    });

    socket.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        socket.close();
        reject(new Error("服务端返回了无法解析的数据"));
        return;
      }

      if (message.type === "start") {
        handlers.onStart?.(message);
      }
      if (message.type === "token") {
        handlers.onToken?.(message.token || "", message);
      }
      if (message.type === "error") {
        socket.close();
        reject(new Error(message.error || "流式回答失败"));
      }
      if (message.type === "end") {
        completed = true;
        handlers.onEnd?.(message);
        socket.close();
        resolve(message);
      }
    });

    socket.addEventListener("error", () => {
      reject(new Error("无法建立流式回答连接"));
    });

    socket.addEventListener("close", () => {
      if (!completed) {
        handlers.onClose?.();
      }
    });
  });
}
