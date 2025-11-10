import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App"; // App completo com autenticação
import { ConfigProvider } from "@/lib/config-initializer";
import "./index.css";

// Debug: Log environment variables
if (import.meta.env.DEV) {
  console.warn('[Dev] Environment:', import.meta.env.MODE);
  console.warn('[Dev] API URL:', import.meta.env.VITE_API_BASE_URL);
  console.warn('[Dev] Firebase project:', import.meta.env['VITE_FIREBASE_PROJECT_ID']);
}

// Global error handling for unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  
  // Prevent the default behavior (error overlay)
  event.preventDefault();
  
  // Check if it's a WebSocket or network error (non-critical)
  if (event.reason?.message?.includes('WebSocket') || 
      event.reason?.message?.includes('ws://') ||
      event.reason?.message?.includes('wss://') ||
      event.reason?.message?.includes('Failed to fetch') ||
      event.reason?.message?.includes('NetworkError')) {
    console.warn('Non-critical error handled gracefully:', event.reason.message);
    return;
  }
  
  // For other errors, log but don't show overlay
  console.error('Promise rejection handled:', event.reason);
});

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
