import {Mark} from '@tiptap/core';
export const ClaimMark = Mark.create({name:'claimReference',addAttributes(){return {reference:{default:null}}},parseHTML(){return [{tag:'span[data-claim-ref]'}]},renderHTML({HTMLAttributes}){return ['span',{'data-claim-ref':HTMLAttributes.reference,class:'claim-anchor'},0]}});
