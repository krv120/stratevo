'use strict';
// In-page integration hooks only. No storage, network transport, identifiers or field values.
window.StratevoStages=Object.freeze({emit(name){if(['assessment_started','assessment_reviewed','inquiry_submitting','inquiry_saved'].includes(name))document.dispatchEvent(new CustomEvent('stratevo:stage',{detail:Object.freeze({name,version:1})}));}});
