import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App"; // App completo com autenticação
import { ConfigProvider } from "@/lib/config-initializer";
// import App from "./AppDebug";
// import App from "./AppSimple";
import "./index.css";

// Debug: Log environment variables
if (import.meta.env.DEV) {
  console.warn('[Dev] Environment:', import.meta.env.MODE);
  console.warn('[Dev] API URL:', import.meta.env.VITE_API_BASE_URL);
  console.warn('[Dev] Supabase URL:', import.meta.env.VITE_SUPABASE_URL);
}

const rootElement = document.getElementById("root");

if (!rootElement) {
  document.body.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; height: 100vh; font-family: system-ui;">
      <div style="text-align: center;">
        <h1 style="color: red;">Erro: Elemento root não encontrado</h1>
        <p>Por favor, verifique o arquivo index.html</p>
      </div>
    </div>
  `;
} else {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </React.StrictMode>
  );
}
