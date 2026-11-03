import {cpSync,mkdirSync,existsSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const original=resolve(root,'wangzhan/baiqipu.com-source-20260424-194149');
const output=resolve(root,'frontend/dist');
const backup=resolve(root,'runtime/ui-build-before-original-restore');
if(!original.startsWith(root)||!output.startsWith(root)||!backup.startsWith(root))throw new Error('Workspace boundary');
if(existsSync(output)&&!existsSync(backup)){mkdirSync(backup,{recursive:true});cpSync(output,backup,{recursive:true});}
mkdirSync(output,{recursive:true});
cpSync(original,output,{recursive:true});
console.log('Packaged original Baiqipu interface unchanged. Redesign is not the default.');
