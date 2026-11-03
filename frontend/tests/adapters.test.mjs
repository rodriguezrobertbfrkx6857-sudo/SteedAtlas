import test from 'node:test';
import assert from 'node:assert/strict';
import {toRows,applyRows} from '../src/timeline.mjs';
import {getSchema} from '@tiptap/core';
import {Transform} from '@tiptap/pm/transform';
import StarterKit from '@tiptap/starter-kit';
import {ClaimMark} from '../src/claim-mark.ts';
test('three-track canonical timeline round trip retains exact integer frames',()=>{
 const project={fps_num:24,audio_asset_ids:['audio'],scenes:[{id:'s1',duration_ticks:25,text:'中文'},{id:'s2',duration_ticks:71,text:'第二幕'},{id:'s3',duration_ticks:49,text:'第三幕'}]};
 assert.deepEqual(applyRows(project,toRows(project)),project);
 assert.equal(toRows(project).length,3);
 const rows=toRows(project);rows[0].actions[1].end+=1/24;
 assert.equal(applyRows(project,rows).scenes[1].duration_ticks,72);
});
test('invalid ranges are rejected',()=>{
 const p={fps_num:24,audio_asset_ids:[],scenes:[{id:'s1',duration_ticks:24}]};const rows=toRows(p);rows[0].actions[0].end=-1;
 assert.throws(()=>applyRows(p,rows));
});
test('Tiptap Chinese claim anchor survives document JSON persistence and local edit',()=>{
 const schema=getSchema([StarterKit,ClaimMark]);
 const mark=schema.marks.claimReference.create({reference:'claim-1@2'});
 const doc=schema.node('doc',null,[schema.node('paragraph',null,[schema.text('赤兔名马',[mark])])]);
 const edited=new Transform(doc).replaceWith(2,3,schema.text('菟',[mark])).doc;
 const restored=schema.nodeFromJSON(JSON.parse(JSON.stringify(edited.toJSON())));
 assert.equal(restored.firstChild.firstChild.marks[0].attrs.reference,'claim-1@2');
 assert.equal(restored.textContent,'赤菟名马');
});
