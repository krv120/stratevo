'use strict';
/* Content Studio: one validated, budget-checked fal.ai video job at a time.
   The browser never sees FAL_KEY: it only talks to this app's authenticated API. */
(() => {
  const { api, node } = window.StratevoUI || {};
  const root = document.getElementById('content-studio');
  const workspace = document.getElementById('admin-workspace');
  if (!root || !workspace || !api) return;

  const state = { status: null, jobs: [], signature: '', timer: null, started: false, clientKey: '', pollingUntil: 0 };

  const section = node('section', undefined, 'panel');
  const title = node('h2', 'Content Studio · AI video');
  const intro = node('p', 'Generate a single marketing clip through fal.ai, review it here, and keep the job id, spend and status on record. Nothing is published and no batch is created.');
  const config = node('p', undefined, 'small');
  config.setAttribute('role', 'status');
  config.setAttribute('aria-live', 'polite');

  const form = node('form');
  form.id = 'video-job-form';
  form.method = 'post';
  const formStatus = node('p', undefined, 'form-status');
  formStatus.id = 'video-job-status';
  formStatus.setAttribute('role', 'status');

  function field(labelText, input, help) {
    const wrap = node('div', undefined, 'field');
    const label = node('label', labelText);
    const id = input.id;
    label.setAttribute('for', id);
    wrap.append(label, input);
    if (help) wrap.append(node('p', help, 'small'));
    return wrap;
  }

  const prompt = node('textarea');
  prompt.id = 'video-prompt';
  prompt.name = 'prompt';
  prompt.required = true;
  prompt.rows = 5;
  prompt.minLength = 10;
  prompt.maxLength = 2000;
  prompt.placeholder = 'Subject, setting, action, camera movement and lighting. Example: a slow push-in on a matte aluminium bracket on a workshop bench, soft window light, shallow depth of field.';
  prompt.setAttribute('aria-describedby', 'video-prompt-help');

  const negative = node('input');
  negative.id = 'video-negative';
  negative.name = 'negative_prompt';
  negative.maxLength = 300;
  negative.placeholder = 'Optional: blur, warped text, extra limbs';

  const model = node('select');
  model.id = 'video-model';
  model.name = 'model';

  const duration = node('select');
  duration.id = 'video-duration';
  duration.name = 'duration_seconds';

  const aspect = node('select');
  aspect.id = 'video-aspect';
  aspect.name = 'aspect_ratio';

  const submit = node('button', 'Generate video', 'primary');
  submit.type = 'submit';

  const cost = node('p', undefined, 'small');
  cost.id = 'video-cost';

  form.append(
    field('Prompt', prompt),
    (() => { const p = node('p', 'Describe one shot. Text overlays and brand claims are not added by the model.', 'small'); p.id = 'video-prompt-help'; return p; })(),
    field('Negative prompt (optional)', negative),
    field('Model', model),
    field('Duration', duration),
    field('Aspect ratio', aspect),
    cost,
    submit,
    formStatus
  );

  const budgetLine = node('p', undefined, 'small');
  const jobsWrap = node('div');
  jobsWrap.id = 'video-jobs';
  jobsWrap.className = 'studio-jobs';
  const refresh = node('button', 'Refresh job list', 'secondary');
  refresh.type = 'button';

  section.append(title, intro, config, form, budgetLine, refresh, jobsWrap);
  root.append(section);

  const models = () => (state.status && state.status.models) || [];
  const modelEntry = () => models().find((entry) => entry.id === model.value) || models()[0];

  function money(value) {
    return '$' + Number(value || 0).toFixed(2);
  }

  function fillModels() {
    model.replaceChildren();
    for (const entry of models()) {
      const option = node('option', entry.label + ' · $' + entry.documented_per_second_usd.toFixed(2) + '/s');
      option.value = entry.id;
      model.append(option);
    }
    if (state.status && state.status.default_model) model.value = state.status.default_model;
    fillDurations();
  }

  function fillDurations() {
    const entry = modelEntry();
    if (!entry) return;
    const previous = Number(duration.value);
    duration.replaceChildren();
    for (const seconds of entry.durations) {
      const option = node('option', seconds + ' seconds');
      option.value = String(seconds);
      duration.append(option);
    }
    duration.value = entry.durations.includes(previous) ? String(previous) : String(entry.durations[0]);
    fillAspects(entry);
    updateCost();
  }

  function fillAspects(entry) {
    const previous = aspect.value;
    aspect.replaceChildren();
    for (const ratio of entry.aspect_ratios) {
      const option = node('option', ratio);
      option.value = ratio;
      aspect.append(option);
    }
    aspect.value = entry.aspect_ratios.includes(previous) ? previous : entry.aspect_ratios[0];
  }

  function updateCost() {
    const entry = modelEntry();
    if (!entry) return;
    const seconds = Number(duration.value) || entry.durations[0];
    const estimate = entry.documented_per_second_usd * seconds;
    cost.textContent = 'Estimated cost ' + money(estimate) + ' for ' + seconds + 's at $' +
      entry.documented_per_second_usd.toFixed(2) + '/s (documented rate; fal.ai billing is authoritative).';
  }

  function renderConfig() {
    const status = state.status;
    if (!status) return;
    const budget = status.budget || {};
    if (status.configured) {
      config.textContent = 'FAL_KEY is configured on the server. Spending committed this month: ' +
        money(budget.spent_usd) + ' of ' + money(budget.limit_usd) + '; remaining ' + money(budget.remaining_usd) + '.';
    } else {
      config.replaceChildren();
      config.append(node('strong', 'FAL_KEY is not configured, so generation is disabled. '));
      config.append(node('span', 'Add it as a server-side environment variable in your hosting provider — Vercel: Project > Settings > Environment Variables > FAL_KEY (Production), then Redeploy. Never put the key in this page, in source control or in a public variable. See docs/FAL-VIDEO-STUDIO.md.'));
    }
    budgetLine.textContent = 'Per-job cap ' + money(budget.max_job_usd) + ' · budget window ' + (budget.window || '') +
      ' · price source ' + (status.price_checked ? 'live fal.ai pricing API with a reviewed fallback checked ' + status.price_checked : 'reviewed table') +
      ' · callbacks ' + (status.webhook_configured ? 'enabled' : 'not configured (status polling only)') + '.';
    if (status.storage && status.storage.durable === false) {
      budgetLine.textContent += ' Storage is not durable: async jobs are blocked outside local development.';
    }
    submit.disabled = !status.configured;
  }

  function timeAgo(epoch) {
    const seconds = Math.max(0, Math.floor(Date.now() / 1000) - epoch);
    if (seconds < 60) return seconds + 's ago';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    return Math.floor(seconds / 3600) + 'h ago';
  }

  function jobCard(job) {
    const card = node('article', undefined, 'manager-row');
    const head = node('p');
    head.append(node('span', job.status.replaceAll('_', ' ').toUpperCase(), 'badge'));
    head.append(node('span', ' ' + job.model_label + ' · ' + job.duration_seconds + 's · ' + job.aspect_ratio + ' · ' + timeAgo(job.created_at)));
    card.append(head);

    if (job.status === 'queued' && job.queue_position >= 0) {
      card.append(node('p', 'Queue position ' + job.queue_position + '. This can take a few minutes.'));
    }
    if (job.status === 'in_progress' || job.status === 'retrieving') {
      card.append(node('p', 'fal.ai is rendering the clip. Leave this page open or come back later; the job is stored.'));
    }

    const promptText = node('p', job.prompt);
    promptText.className = 'preserve-lines';
    card.append(promptText);

    if (job.status === 'completed' && job.video_url) {
      const video = node('video');
      video.className = 'studio-video';
      video.controls = true;
      video.preload = 'metadata';
      video.playsInline = true;
      video.src = job.video_url;
      const link = node('a', 'Open video in a new tab', 'secondary');
      link.href = job.video_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      const copy = node('button', 'Copy URL', 'secondary');
      copy.type = 'button';
      copy.onclick = async () => {
        try {
          await navigator.clipboard.writeText(job.video_url);
          copy.textContent = 'Copied';
        } catch {
          copy.textContent = 'Select the link to copy';
        }
      };
      card.append(video, link, copy);
      const note = node('p', 'Generated media URLs expire. Download the clip if you need to keep it.', 'small');
      card.append(note);
    }

    const facts = node('p', undefined, 'small');
    facts.textContent = 'Cost ' + money(job.cost_usd) + ' (' + (job.cost_basis || 'unknown basis') + ')' +
      (job.fal_request_id ? ' · fal request ' + job.fal_request_id : '') +
      (job.attempts > 1 ? ' · attempt ' + job.attempts : '');
    card.append(facts);

    if (job.error) {
      const error = node('p', job.error);
      error.className = 'field-error';
      card.append(error);
    }

    const actions = node('div', undefined, 'actions');
    const active = ['reserved', 'queued', 'in_progress', 'retrieving', 'canceling'].includes(job.status);
    if (active) {
      const check = node('button', 'Check status', 'secondary');
      check.type = 'button';
      check.onclick = () => withBusy(check, async () => { await syncJob(job.id); await loadJobs(); });
      actions.append(check);
    }
    if (active && !['canceling'].includes(job.status)) {
      const stop = node('button', 'Cancel job', 'secondary');
      stop.type = 'button';
      stop.onclick = () => withBusy(stop, () => act('/api/admin/video/cancel', { id: job.id }, 'Cancellation requested.'));
      actions.append(stop);
    }
    if (['failed', 'canceled', 'submit_failed'].includes(job.status)) {
      const again = node('button', 'Retry job', 'secondary');
      again.type = 'button';
      again.onclick = () => withBusy(again, () => act('/api/admin/video/retry', { id: job.id }, 'Retry submitted.'));
      actions.append(again);
    }
    if (actions.childNodes.length) card.append(actions);
    return card;
  }

  async function withBusy(button, action) {
    if (button.disabled) return;
    button.disabled = true;
    try {
      await action();
    } catch (error) {
      formStatus.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function act(path, payload, message) {
    const result = await api(path, payload);
    if (message) formStatus.textContent = message;
    await loadJobs();
    await loadStatus();
    schedulePoll();
    return result;
  }

  function renderJobs() {
    // Re-render only when something actually changed, so a clip that is
    // already playing is not torn down by a poll of another job.
    const signature = JSON.stringify(state.jobs.map((job) => [job.id, job.status, job.updated_at, job.video_url, job.cost_usd]));
    if (signature === state.signature) return;
    state.signature = signature;
    jobsWrap.replaceChildren();
    if (!state.jobs.length) {
      jobsWrap.append(node('p', 'No video jobs yet. The first successful generation will appear here with its video, job id and cost.'));
      return;
    }
    for (const job of state.jobs) jobsWrap.append(jobCard(job));
  }

  async function loadStatus() {
    try {
      state.status = await api('/api/admin/video/status');
      if (!model.options.length) fillModels();
      renderConfig();
    } catch (error) {
      config.textContent = error.message;
    }
  }

  async function loadJobs() {
    const result = await api('/api/admin/video/jobs');
    state.jobs = result.jobs;
    renderJobs();
  }

  async function syncJob(id) {
    await api('/api/admin/video/sync', { id });
  }

  function activeJobs() {
    return state.jobs.filter((job) => ['reserved', 'queued', 'in_progress', 'retrieving', 'canceling'].includes(job.status));
  }

  function schedulePoll() {
    clearTimeout(state.timer);
    state.timer = null;
    const active = activeJobs();
    if (!active.length) return;
    if (!state.pollingUntil) state.pollingUntil = Date.now() + 30 * 60 * 1000;
    if (Date.now() > state.pollingUntil) return;
    state.timer = setTimeout(async () => {
      for (const job of active.slice(0, 3)) {
        try {
          await syncJob(job.id);
        } catch (error) {
          formStatus.textContent = error.message;
        }
      }
      await loadJobs();
      await loadStatus();
      schedulePoll();
    }, 6000);
  }

  async function start() {
    if (state.started) return;
    state.started = true;
    try {
      await loadStatus();
      await loadJobs();
      schedulePoll();
    } catch (error) {
      formStatus.textContent = error.message;
    }
  }

  form.onsubmit = async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    if (!state.clientKey) state.clientKey = (crypto.randomUUID ? crypto.randomUUID() : window.StratevoUI.key());
    submit.disabled = true;
    submit.textContent = 'Submitting to fal.ai…';
    formStatus.textContent = 'Submitting to fal.ai…';
    try {
      const result = await api('/api/admin/video/jobs', {
        prompt: prompt.value,
        negative_prompt: negative.value,
        model: model.value,
        duration_seconds: Number(duration.value),
        aspect_ratio: aspect.value,
        client_key: state.clientKey
      }, 45000);
      state.clientKey = '';
      formStatus.textContent = result.deduplicated
        ? 'This exact request was already submitted; the existing job is shown.'
        : 'Job ' + result.job.id + ' accepted by fal.ai. Watching for completion.';
      state.pollingUntil = 0;
      await loadJobs();
      await loadStatus();
      schedulePoll();
    } catch (error) {
      // Keep the same client key so a retry cannot create a second charge.
      formStatus.textContent = error.message;
    } finally {
      submit.disabled = !(state.status && state.status.configured);
      submit.textContent = 'Generate video';
    }
  };

  model.onchange = fillDurations;
  duration.onchange = updateCost;
  refresh.onclick = () => withBusy(refresh, async () => {
    state.pollingUntil = 0;
    state.signature = '';
    await loadStatus();
    await loadJobs();
    schedulePoll();
  });

  // Fetch only after sign-in: the workspace section is hidden until then.
  if (!workspace.hidden) start();
  new MutationObserver(() => {
    if (!workspace.hidden && !state.started) start();
  }).observe(workspace, { attributes: true, attributeFilter: ['hidden'] });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(state.timer);
    else schedulePoll();
  });
})();
