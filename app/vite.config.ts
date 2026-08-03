import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { port: 5180, host: "127.0.0.1" },
  build: {
    rollupOptions: {
      input: {
        home: resolve(__dirname, "index.html"),
        drafts: resolve(__dirname, "drafts.html"),
        autoedit: resolve(__dirname, "autoedit.html"),
        voices: resolve(__dirname, "voices.html"),
        avatars: resolve(__dirname, "avatars.html"),
        envCheck: resolve(__dirname, "env-check.html"),
        templates: resolve(__dirname, "templates.html"),
        blog: resolve(__dirname, "blog.html"),
        ppt: resolve(__dirname, "ppt.html"),
        record: resolve(__dirname, "record.html"),
        translate: resolve(__dirname, "translate.html"),
        pricing: resolve(__dirname, "pricing.html"),
        login: resolve(__dirname, "login.html"),
        signup: resolve(__dirname, "signup.html"),
        files: resolve(__dirname, "files.html"),
        playground: resolve(__dirname, "playground.html"),        characters: resolve(__dirname, "characters.html"),
        features: resolve(__dirname, "features.html"),
        useCases: resolve(__dirname, "use-cases.html"),
        billing: resolve(__dirname, "billing.html"),
        share: resolve(__dirname, "share.html"),
      },
    },
  },
});
