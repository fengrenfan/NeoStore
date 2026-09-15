import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./lib/auth";
import "./index.css";

/**
 * `basename` matches `base` in `vite.config.ts`: Caddy strips `/admin` before
 * proxying, but the browser still carries it in the address bar.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Admin data changes on operator actions, not on a timer; refetching on
      // every window focus mostly produces flicker.
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5_000,
    },
  },
});

const container = document.getElementById("root");
if (!container) throw new Error("#root is missing from index.html");

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/admin">
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
