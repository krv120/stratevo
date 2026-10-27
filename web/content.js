'use strict';
/* Content pipeline: 40 faceless vertical videos, reviewed, captioned and scheduled.
   The browser never sees FAL_KEY or BUFFER_API_KEY; it only calls this app's
   authenticated admin API. Nothing is marked scheduled until Buffer returns a
   post id, and no paid generation starts without an explicit click. */
(() => {
  const { api, node } = window.StratevoUI || {};
  const root = document.getElementById('content-pipeline');
  const workspace = document.getElementById('admin-workspace');
  if (!root || !workspace || !api) return;

  const state = { overview: null, filter: 'draft', timer: null, busy: '', plan: null, notice: '' };

  const section = node('section', undefined, 'panel');
  section.id = 'pipeline';
  const title = node('h2', 'Production line · 40 videos');
  const intro = node('p', 'Generate a series of distinct ideas, approve the ones you want, let the worker create and caption the vertical clips, then schedule them in Europe/Athens through Buffer. Every paid step is budget-checked before it runs.');
  const statusLine = node('p', undefined, 'small');
  statusLine.setAttribute('role', 'status');
  statusLine.setAttribute('aria-live', 'polite');
  const notice = node('p', undefined, 'notice');
  notice.setAttribute('role', 'alert');
  notice.hidden = true;

  const setup = node('div', undefined, 'split align-start');
  section.append(title, intro, statusLine, notice, setup);
  root.append(section);

  function money(value) { return '$' + Number(value || 0).toFixed(2); }
  function fail(error) {
    notice.textContent = error && error.message ? error.message : 'The request could not be completed.';
    notice.hidden = false;
  }
  function clearNotice() { notice.hidden = true; notice.textContent = ''; }

  function field(labelText, input, help) {
    const wrap = node('div', undefined, 'field');
    const label = node('label', labelText);
    label.setAttribute('for', input.id);
    wrap.append(label, input);
    if (help) wrap.append(node('p', help, 'small'));
    return wrap;
  }

  /* ---------------------------------------------------------------- setup */
  const setupForm = node('form');
  setupForm.id = 'pipeline-series-form';
  const nameInput = node('input');
  nameInput.id = 'pipeline-name'; nameInput.name = 'name'; nameInput.maxLength = 120;
  nameInput.value = 'STRATEVO sourcing series';
  const countInput = node('input');
  countInput.id = 'pipeline-count'; countInput.name = 'count'; countInput.type = 'number';
  countInput.min = '1'; countInput.max = '200'; countInput.value = '40';
  const modelSelect = node('select');
  modelSelect.id = 'pipeline-model'; modelSelect.name = 'model';
  const durationSelect = node('select');
  durationSelect.id = 'pipeline-duration'; durationSelect.name = 'duration_seconds';
  const resolutionSelect = node('select');
  resolutionSelect.id = 'pipeline-resolution'; resolutionSelect.name = 'resolution';
  const costLine = node('p', undefined, 'small');
  costLine.id = 'pipeline-cost';
  const createButton = node('button', 'Create idea series', 'primary');
  createButton.type = 'submit';
  const setupStatus = node('p', undefined, 'form-status');
  setupStatus.setAttribute('role', 'status');

  setupForm.append(
    field('Series name', nameInput),
    field('Ideas to write', countInput, '40 gives one month of two daily posts. Scripts stay under 34 words.'),
    field('Video model', modelSelect, 'MiniMax H3 Max Turbo is the cheapest suitable vertical model found (768P list $0.04/s).'),
    field('Seconds per clip', durationSelect),
    field('Resolution', resolutionSelect),
    costLine,
    createButton,
    setupStatus
  );

  const sidePanel = node('aside', undefined, 'panel');
  const sideTitle = node('h3', 'Cost before you spend');
  const sideBody = node('div');
  sidePanel.append(sideTitle, sideBody);

  const setupBox = node('div');
  setupBox.append(setupForm);
  setup.append(setupBox, sidePanel);

  const controls = node('div', undefined, 'actions');
  const queueButton = node('button', 'Queue approved videos', 'primary');
  queueButton.type = 'button';
  const scheduleButton = node('button', 'Plan 30 days', 'secondary');
  scheduleButton.type = 'button';
  const publishButton = node('button', 'Send planned posts to Buffer', 'secondary');
  publishButton.type = 'button';
  const tickButton = node('button', 'Run worker now', 'secondary');
  tickButton.type = 'button';
  const smokeButton = node('button', 'One-video real test', 'secondary');
  smokeButton.type = 'button';
  const nightlyButton = node('button', 'Run one night now', 'secondary');
  nightlyButton.type = 'button';
  const refreshButton = node('button', 'Refresh', 'secondary');
  refreshButton.type = 'button';
  controls.append(queueButton, scheduleButton, publishButton, tickButton, smokeButton, nightlyButton, refreshButton);
  section.append(controls);

  const countsWrap = node('ul', undefined, 'checklist');
  countsWrap.id = 'pipeline-counts';
  section.append(countsWrap);

  const filters = node('div', undefined, 'actions');
  const filterNames = [['draft', 'To review'], ['approved', 'Approved'], ['video_pending', 'Generating'],
    ['video_ready', 'Captioned'], ['ready_to_publish', 'Ready'], ['scheduled', 'Scheduled'], ['failed', 'Failed'], ['all', 'All']];
  for (const [key, label] of filterNames) {
    const button = node('button', label, 'secondary');
    button.type = 'button';
    button.dataset.filter = key;
    button.addEventListener('click', () => { state.filter = key; renderIdeas(); });
    filters.append(button);
  }
  section.append(filters);

  const ideaWrap = node('div', undefined, 'studio-jobs');
  ideaWrap.id = 'pipeline-ideas';
  section.append(ideaWrap);

  const publishTitle = node('h3', 'Buffer schedule');
  const publishWrap = node('div');
  publishWrap.id = 'pipeline-publications';
  section.append(publishTitle, publishWrap);

  /* -------------------------------------------------------------- helpers */
  const models = () => (state.overview && state.overview.status && state.overview.status.models) || [];
  const currentModel = () => models().find((entry) => entry.id === modelSelect.value) || models()[0];

  function fillModels() {
    modelSelect.replaceChildren();
    for (const entry of models()) {
      const option = node('option', entry.label);
      option.value = entry.id;
      modelSelect.append(option);
    }
    if (!models().length) {
      const option = node('option', 'MiniMax H3 Max Turbo');
      option.value = 'minimax-h3-max-turbo';
      modelSelect.append(option);
    }
    fillDurations();
  }

  function fillDurations() {
    const entry = currentModel();
    const values = entry ? entry.durations : [5, 10];
    const previous = Number(durationSelect.value);
    durationSelect.replaceChildren();
    for (const seconds of values) {
      const option = node('option', seconds + ' seconds');
      option.value = String(seconds);
      durationSelect.append(option);
    }
    durationSelect.value = values.includes(previous) ? String(previous) : String(values.includes(10) ? 10 : values[0]);
    fillResolutions();
  }

  function fillResolutions() {
    const entry = currentModel();
    const values = entry && entry.resolutions && entry.resolutions.length ? entry.resolutions : [''];
    resolutionSelect.replaceChildren();
    for (const value of values) {
      const option = node('option', value || 'Fixed price');
      option.value = value;
      resolutionSelect.append(option);
    }
    resolutionSelect.value = values.includes('768P') ? '768P' : values[0];
    updateCost();
  }

  async function updateCost() {
    const params = new URLSearchParams({
      model: modelSelect.value, duration: durationSelect.value,
      resolution: resolutionSelect.value, count: countInput.value || '40'
    });
    try {
      const plan = await api('/api/admin/content/estimate?' + params.toString());
      state.plan = plan;
      costLine.textContent = plan.videos + ' videos × ' + plan.duration_seconds + 's at ' + plan.resolution +
        ' = ' + money(plan.total_usd) + ' (list price ' + money(plan.unit_price_usd) + '/s). ' +
        'Budget ' + money(plan.budget_limit_usd) + ', spent ' + money(plan.budget_spent_usd) +
        ', so ' + plan.affordable_videos + ' videos fit the remaining allowance.';
      renderSide();
    } catch (error) { fail(error); }
  }

  function renderSide() {
    const plan = state.plan;
    sideBody.replaceChildren();
    if (!plan) { sideBody.append(node('p', 'Loading prices…', 'small')); return; }
    const list = node('ul', undefined, 'checklist');
    list.append(node('li', plan.videos + ' clips × ' + plan.duration_seconds + 's = ' + money(plan.total_usd) + ' at list price'));
    if (plan.promotional_total_usd) {
      list.append(node('li', money(plan.promotional_total_usd) + ' at the current promotional rate' +
        (plan.promo_ends ? ' (ends ' + plan.promo_ends + ')' : '')));
    }
    list.append(node('li', 'Monthly generation limit ' + money(plan.budget_limit_usd) + ', ' + money(plan.budget_remaining_usd) + ' remaining'));
    list.append(node('li', 'Buffer Essentials: $6 per channel/month for unlimited queued posts; the free plan allows 10 queued posts per channel'));
    list.append(node('li', 'Caption rendering is local (ffmpeg) and adds no API cost'));
    sideBody.append(list);
    sideBody.append(node('p', plan.note || '', 'small'));
  }

  modelSelect.addEventListener('change', fillDurations);
  durationSelect.addEventListener('change', updateCost);
  resolutionSelect.addEventListener('change', updateCost);
  countInput.addEventListener('change', updateCost);

  /* --------------------------------------------------------------- render */
  function badge(text) { return node('span', String(text).replaceAll('_', ' ').toUpperCase(), 'badge'); }

  function renderStatus() {
    const data = state.overview;
    if (!data) return;
    const series = data.series;
    const cost = data.cost || {};
    const publishing = data.publishing || {};
    const worker = data.worker || {};
    if (!series) {
      statusLine.textContent = 'No series yet. Create the idea series to start.';
      return;
    }
    const channelText = publishing.channels && publishing.channels.length
      ? publishing.channels.map((channel) => channel.display_name || channel.name || channel.service).join(', ')
      : (publishing.error || (publishing.configured ? 'no TikTok/Instagram channel found' : 'BUFFER_API_KEY not set'));
    const nightly = data.nightly || {};
    const speech = data.voice || {};
    statusLine.textContent = series.name + ' · ' + series.target_count + ' ideas · ' + cost.videos + ' videos at ' +
      money(cost.per_video_usd) + ' each (' + money(cost.total_usd) + ' total, ' + money(cost.budget_remaining_usd) +
      ' left this month) · tonight ' + (nightly.generated_tonight || 0) + '/' + (nightly.count || 0) +
      (nightly.auto_approve ? ' auto-approved' : ' manual approval') +
      ' · voice ' + (speech.enabled ? speech.label + ' (' + money(speech.spent_usd) + ' of ' + money(speech.limit_usd) + ')' : 'off') +
      ' · end card ' + (data.cta || '') +
      ' · Buffer: ' + (publishing.enabled ? 'sending enabled' : 'sending disabled') + ' (' + channelText +
      ') · worker: ' + worker.pending + ' queued, ' + worker.running + ' running, ' + worker.dead + ' failed permanently · ffmpeg ' + (worker.ffmpeg || 'unknown');
  }

  function renderCounts() {
    countsWrap.replaceChildren();
    const counts = (state.overview && state.overview.counts) || {};
    for (const [key, value] of Object.entries(counts)) {
      if (!value) continue;
      const item = node('li');
      item.append(badge(key), node('span', ' ' + value));
      countsWrap.append(item);
    }
    if (!countsWrap.childNodes.length) countsWrap.append(node('li', 'No ideas yet.'));
  }

  function ideaCard(idea) {
    const card = node('article', undefined, 'manager-row');
    const head = node('p');
    head.append(badge(idea.status), node('span', ' #' + idea.position + ' · ' + idea.topic + ' · ' + idea.angle +
      ' · ~' + idea.reading_seconds + 's read'));
    card.append(head);
    const hook = node('p');
    hook.append(node('strong', idea.hook));
    card.append(hook);
    const script = node('p', idea.script);
    script.className = 'preserve-lines';
    card.append(script);

    const details = node('details');
    details.append(node('summary', 'Prompt and captions'));
    const prompt = node('p', idea.video_prompt);
    prompt.className = 'preserve-lines';
    details.append(prompt);
    details.append(node('p', 'TikTok: ' + idea.tiktok_caption + ' ' + idea.tiktok_hashtags, 'small'));
    details.append(node('p', 'Instagram: ' + idea.instagram_caption + ' ' + idea.instagram_hashtags, 'small'));
    if (idea.caption_error) details.append(node('p', 'Last error: ' + idea.caption_error, 'small'));
    card.append(details);

    if (idea.video_url) {
      const video = node('video');
      video.className = 'studio-video';
      video.controls = true;
      video.preload = 'metadata';
      video.playsInline = true;
      video.src = idea.video_url;
      card.append(video);
      const link = node('a', 'Open clip', 'secondary');
      link.href = idea.video_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      card.append(link);
    }

    const actions = node('div', undefined, 'actions');
    if (idea.status === 'draft' || idea.status === 'rejected') {
      const approve = node('button', 'Approve', 'primary');
      approve.type = 'button';
      approve.addEventListener('click', () => decide(idea.id, 'approve'));
      const reject = node('button', 'Reject', 'secondary');
      reject.type = 'button';
      reject.addEventListener('click', () => decide(idea.id, 'reject'));
      const regen = node('button', 'Regenerate', 'secondary');
      regen.type = 'button';
      regen.addEventListener('click', () => regenerate(idea.id));
      actions.append(approve, reject, regen);
    }
    if (idea.status === 'failed' || idea.status === 'rejected') {
      const reset = node('button', 'Return to review', 'secondary');
      reset.type = 'button';
      reset.addEventListener('click', () => decide(idea.id, 'approve'));
      actions.append(reset);
    }
    if (actions.childNodes.length) card.append(actions);
    return card;
  }

  function renderIdeas() {
    ideaWrap.replaceChildren();
    const ideas = (state.overview && state.overview.ideas) || [];
    const shown = ideas.filter((idea) => state.filter === 'all' || idea.status === state.filter);
    for (const button of filters.querySelectorAll('button')) {
      button.setAttribute('aria-pressed', String(button.dataset.filter === state.filter));
    }
    if (!shown.length) {
      ideaWrap.append(node('p', 'Nothing in this state.', 'small'));
      return;
    }
    for (const idea of shown) ideaWrap.append(ideaCard(idea));
  }

  function renderPublications() {
    publishWrap.replaceChildren();
    const rows = (state.overview && state.overview.publications) || [];
    if (!rows.length) {
      publishWrap.append(node('p', 'No planned posts yet. Caption the clips, then plan the 30-day calendar.', 'small'));
      return;
    }
    const list = node('ul', undefined, 'checklist');
    for (const row of rows.slice(0, 60)) {
      const item = node('li');
      item.append(badge(row.status), node('span', ' #' + row.idea_position + ' · ' + row.platform +
        ' · ' + (row.local_slot || '') + (row.buffer_post_id ? ' · Buffer ' + row.buffer_post_id : '') +
        (row.error_message ? ' · ' + row.error_message : '')));
      list.append(item);
    }
    publishWrap.append(list);
    publishWrap.append(node('p', 'A post only counts as scheduled when Buffer returns a post id; planned rows are local placeholders.', 'small'));
  }

  async function load() {
    try {
      state.overview = await api('/api/admin/content/overview');
      renderStatus(); renderCounts(); renderIdeas(); renderPublications();
    } catch (error) { fail(error); }
  }

  /* --------------------------------------------------------------- actions */
  function withBusy(button, label, task) {
    return async () => {
      if (state.busy) return;
      state.busy = label;
      const original = button.textContent;
      button.disabled = true;
      button.textContent = label;
      clearNotice();
      try { await task(); } catch (error) { fail(error); }
      finally { state.busy = ''; button.disabled = false; button.textContent = original; }
    };
  }

  async function decide(id, action) {
    if (action === 'approve' && !window.confirm('Approve this idea? Generation still needs a separate queue click, which spends money.')) return;
    try {
      await api('/api/admin/content/decide', { id, action });
      await load();
    } catch (error) { fail(error); }
  }

  async function regenerate(id) {
    if (!window.confirm('Replace this concept with a new one? No money is spent.')) return;
    try { await api('/api/admin/content/regenerate', { id }); await load(); } catch (error) { fail(error); }
  }

  setupForm.addEventListener('submit', withBusy(createButton, 'Creating…', async () => {
    setupStatus.textContent = '';
    const result = await api('/api/admin/content/series', {
      name: nameInput.value, count: Number(countInput.value) || 40, model: modelSelect.value,
      duration_seconds: Number(durationSelect.value) || 10, resolution: resolutionSelect.value,
      aspect_ratio: '9:16'
    });
    setupStatus.textContent = 'Created ' + result.created + ' ideas. Nothing has been generated or charged yet.';
    await load();
  }));

  queueButton.addEventListener('click', withBusy(queueButton, 'Queuing…', async () => {
    const overview = state.overview;
    if (!overview || !overview.series) throw new Error('Create a series first.');
    const approved = (overview.counts || {}).approved || 0;
    if (!approved) throw new Error('No approved ideas. Approve ideas before queuing paid generation.');
    const ask = window.prompt('How many approved videos should be queued now? Each one is charged by fal.ai.', String(Math.min(approved, 1)));
    if (ask === null) return;
    const limit = Math.max(1, Math.min(approved, Number(ask) || 0));
    const per = overview.cost ? overview.cost.per_video_usd : 0;
    if (!window.confirm('Queue ' + limit + ' video(s) at about ' + money(per) + ' each (' + money(per * limit) + ')? The monthly limit is enforced server-side.')) return;
    const result = await api('/api/admin/content/generate', { series_id: overview.series.id, limit });
    notice.hidden = false;
    notice.textContent = 'Queued ' + result.queued_count + ' video(s) for ' + money(result.spend_usd) +
      '. ' + (result.skipped.length ? 'Stopped: ' + result.skipped[0].reason : '') +
      (result.failed.length ? ' Failed: ' + result.failed[0].reason : '');
    await load();
  }));

  scheduleButton.addEventListener('click', withBusy(scheduleButton, 'Planning…', async () => {
    const overview = state.overview;
    if (!overview || !overview.series) throw new Error('Create a series first.');
    const result = await api('/api/admin/content/schedule', { series_id: overview.series.id, days: 30, platforms: ['tiktok', 'instagram'] });
    notice.hidden = false;
    notice.textContent = 'Planned ' + result.planned + ' slot(s) for ' + result.ideas + ' clip(s) from ' + result.first_slot +
      ' to ' + result.last_slot + '. ' + result.message;
    await load();
  }));

  publishButton.addEventListener('click', withBusy(publishButton, 'Sending…', async () => {
    const overview = state.overview;
    if (!overview) throw new Error('Nothing to send.');
    const planned = (overview.publications || []).filter((row) => row.status === 'planned');
    if (!planned.length) throw new Error('No planned posts. Plan the calendar first.');
    if (!window.confirm('Submit up to 4 planned posts to Buffer now? Posts are only confirmed when Buffer returns a post id.')) return;
    let confirmed = 0; const errors = [];
    for (const row of planned.slice(0, 4)) {
      try { await api('/api/admin/content/publish', { publication_id: row.id }); confirmed += 1; }
      catch (error) { errors.push(error.message); }
    }
    notice.hidden = false;
    notice.textContent = confirmed + ' post(s) confirmed by Buffer.' + (errors.length ? ' ' + errors[0] : '');
    await load();
  }));

  nightlyButton.addEventListener('click', withBusy(nightlyButton, 'Starting…', async () => {
    const result = await api('/api/admin/content/nightly', { limit: 2 });
    notice.hidden = false;
    notice.textContent = result.submitted + ' video(s) queued' + (result.spend_usd ? ' for ' + money(result.spend_usd) : '') +
      '. ' + (result.reason || 'Tonight\'s target: ' + ((result.nightly || {}).count || 0) + '.');
    await load();
  }));

  tickButton.addEventListener('click', withBusy(tickButton, 'Running…', async () => {
    const result = await api('/api/admin/content/tick', {});
    notice.hidden = false;
    notice.textContent = 'Worker pass: ' + (result.video && result.video.synced ? Object.keys(result.video.synced).length : 0) +
      ' job(s) synced, ' + (result.jobs ? result.jobs.done : 0) + ' task(s) done' +
      (result.errors && result.errors.length ? '. ' + result.errors[0] : '.');
    await load();
  }));

  smokeButton.addEventListener('click', withBusy(smokeButton, 'Starting…', async () => {
    if (!window.confirm('Create and immediately generate ONE 5-second test clip at 768P? ' +
      'This is a real fal.ai charge of about $0.20 (list price), inside the monthly limit.')) return;
    const result = await api('/api/admin/content/smoke', {});
    notice.hidden = false;
    notice.textContent = 'Test video queued for ' + money(result.spend_usd) + ' with job ' +
      (result.queued[0] ? result.queued[0].job_id : '') + '. ' + (result.next || '');
    await load();
  }));

  refreshButton.addEventListener('click', withBusy(refreshButton, 'Refreshing…', load));

  /* ----------------------------------------------------------------- boot */
  async function boot() {
    try {
      const plugin = await api('/api/admin/video/status');
      state.status = plugin;
      fillModels();
      await updateCost();
    } catch (error) { /* status is optional for the pipeline */ }
    await load();
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(() => {
      if (!workspace.hidden && !state.busy && (!state.overview || !state.overview.series ||
        Object.keys((state.overview.counts || {})).some((key) => ['video_pending', 'video_ready', 'caption_pending'].includes(key)))) {
        load();
      }
    }, 20000);
  }

  const observer = new MutationObserver(() => { if (!workspace.hidden) { observer.disconnect(); boot(); } });
  if (workspace.hidden) observer.observe(workspace, { attributes: true, attributeFilter: ['hidden'] });
  else boot();
})();
