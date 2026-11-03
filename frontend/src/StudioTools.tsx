import React from 'react';
import {EditorContent,useEditor} from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import {ClaimMark} from './claim-mark';
import {ReactFlow,Background,Controls} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import '@xzdarcy/react-timeline-editor/dist/react-timeline-editor.css';
export {Timeline} from '@xzdarcy/react-timeline-editor';
type Scene = {id:string;text:string;duration_ticks:number;asset_id:string|null;claim_refs:string[];label:string;period:string;script_doc?:any};
export function FlowGraph({nodes,edges}:{nodes:any[];edges:any[]}){return <ReactFlow nodes={nodes} edges={edges} fitView><Background/><Controls/></ReactFlow>}
export function ScriptEditor({scene,onChange}:{scene:Scene;onChange:(s:Scene)=>void}) {
  const editor=useEditor({immediatelyRender:false,extensions:[StarterKit,ClaimMark],content:scene.script_doc||{type:'doc',content:[{type:'paragraph',content:scene.text?[{type:'text',text:scene.text,marks:scene.claim_refs.map(reference=>({type:'claimReference',attrs:{reference}}))}]:[]}]},
    editorProps:{attributes:{'aria-label':'场景剧本 '+scene.id,role:'textbox'}},onUpdate:({editor})=>onChange({...scene,text:editor.getText(),script_doc:editor.getJSON()})},[scene.id]);
  return <EditorContent editor={editor}/>;
}