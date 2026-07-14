# =====================================================================
# DOCKERFILE PARA FRONTEND (VUE.JS 3 + VITE)
# =====================================================================
# Imagen base Node.js Debian (no Alpine para compatibilidad con rolldown)
# Rolldown requiere bindings precompilados que no funcionan bien en musl
# =====================================================================

FROM node:20-bookworm

# ===================================================================
# CONFIGURACIÓN DEL ENTORNO
# ===================================================================

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Variable de entorno para modo desarrollo
ENV NODE_ENV=development

# ===================================================================
# INSTALACIÓN DE DEPENDENCIAS
# ===================================================================

# Copiar archivos de configuración de npm
# package.json contiene dependencias principales
# package-lock.json asegura versiones exactas reproducibles
COPY package*.json ./

# Limpiar cache de npm y node_modules para evitar problemas de binding nativo
RUN npm cache clean --force && rm -rf node_modules

# Instalar dependencias con npm ci --force para forzar optional dependencies
# rolldown es una optional dependency que necesita forzarse en Docker
RUN npm ci --force

# ===================================================================
# COPIA DEL CÓDIGO FUENTE
# ===================================================================

# Copiar todo el código fuente de la aplicación
COPY . .

# ===================================================================
# EXPOSICIÓN DE PUERTOS
# ===================================================================

# Exponer puerto 5173 para servidor de desarrollo Vite
# Este puerto es donde está disponible la aplicación Vue.js
EXPOSE 5173

# ===================================================================
# COMANDO DE INICIO
# ===================================================================

# Comando por defecto para iniciar servidor de desarrollo Vite
# --host 0.0.0.0 permite acceso desde fuera del contenedor
# En desarrollo, Vite proporciona hot-module-replacement automático
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
