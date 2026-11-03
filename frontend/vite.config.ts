import {defineConfig} from 'vite';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const frontendRoot=fileURLToPath(new URL('.',import.meta.url));
const originalSite=resolve(frontendRoot,'../wangzhan/baiqipu.com-source-20260424-194149');
export default defineConfig(({mode})=>({
  root:mode==='redesign'?frontendRoot:originalSite,
  cacheDir:resolve(frontendRoot,'node_modules/.vite-original'),
  server:{host:'127.0.0.1',port:mode==='resume-rc'?Number(process.env.STEEDATLAS_RC_PORT||5178):mode==='redesign'?5174:mode==='rag-auto'?5176:mode==='rag-qa'?5175:5173,strictPort:true,proxy:{'/api':mode==='resume-rc'?(process.env.STEEDATLAS_RC_API||'http://127.0.0.1:8006'):mode==='rag-auto'?'http://127.0.0.1:8004':mode==='rag-qa'?'http://127.0.0.1:8003':'http://127.0.0.1:8002'}},
  build:{outDir:resolve(frontendRoot,mode==='redesign'?'preview-dist':'dist'),emptyOutDir:false,chunkSizeWarningLimit:850}
}));
