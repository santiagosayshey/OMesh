import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/", // Set the base path for assets
  build: {
    outDir: "build", // Output directory for the build files
  },
});
