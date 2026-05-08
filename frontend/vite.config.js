import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

//what the hell is this below function doing ? 
//what is the mode parameter ? 
//what is the process.cwd() parameter ? 
//what is the "" parameter ? 
//what is the return value of this function ? 
//what is the proxy parameter ? 
//what is the changeOrigin parameter ? 
//what is the target parameter ? 

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Backend FastAPI runs on 8001; MCP server runs on 8000 separately.
  const target = env.VITE_API_BASE || "http://127.0.0.1:8001";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/tree": { target, changeOrigin: true },
        "/preview": { target, changeOrigin: true },
        "/chat": { target, changeOrigin: true }
      }
    }
  };
});

