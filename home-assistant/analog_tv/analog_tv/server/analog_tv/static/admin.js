class AnalogTVAdmin {
  constructor() {
    this.channelForm = document.querySelector("#channelForm");
    this.alertForm = document.querySelector("#alertForm");
    this.settingsForm = document.querySelector("#settingsForm");
    this.broadcastSettingsForm = document.querySelector("#broadcastSettingsForm");
    this.youtubeSettingsForm = document.querySelector("#youtubeSettingsForm");
    this.sourceType = this.channelForm.elements.source_type;
    this.sourceInput = this.channelForm.elements.source;
    this.folderPickerButton =
      document.querySelector("#folderPickerButton");
  }

  async boot() {
    const identityResponse = await fetch("/auth/me", {credentials: "same-origin", cache: "no-store"});
    if (!identityResponse.ok) { window.location.href = "/auth/login"; return; }
    this.identity = await identityResponse.json();
    const who = document.querySelector("#signedInAs");
    if (who) who.textContent = this.identity.username;
    document.querySelector("#analogSignOut")?.addEventListener("click", async () => {
      await this.request("/auth/logout", {method: "POST"});
      window.location.assign("/auth/login");
    });
    document.querySelector("#testWeatherTicker")?.addEventListener("click", () => this.testWeatherTicker());
    this.bindEvents();
    await Promise.all([
      this.loadChannels(),
      this.loadSettings(),
    ]);
  }

  bindEvents() {
    this.channelForm.addEventListener(
      "submit",
      event => this.createChannel(event),
    );
    this.alertForm.addEventListener(
      "submit",
      event => this.createAlert(event),
    );
    this.settingsForm.addEventListener(
      "submit",
      event => this.saveSettings(event),
    );

    this.folderPickerButton.addEventListener(
      "click",
      () => this.selectFolder(),
    );

    this.sourceType.addEventListener(
      "change",
      () => this.updateSourceControls(),
    );

    this.broadcastSettingsForm.addEventListener("submit", event => this.saveExtraSettings(event, this.broadcastSettingsForm, "broadcastStatus"));
    this.youtubeSettingsForm.addEventListener("submit", event => this.saveExtraSettings(event, this.youtubeSettingsForm, "youtubeStatus"));
    document.querySelector("#youtubeConnect").addEventListener("click", () => this.connectYouTube());
    document.querySelector("#youtubeLoadSubs").addEventListener("click", () => this.loadYouTubeSubscriptions());
    document.querySelector("#findLocation")?.addEventListener("click", () => this.searchLocation());
    document.querySelector("#detectIp")?.addEventListener("click", () => this.detectIpLocation());
    document.querySelector("#createWeatherChannel")?.addEventListener("click", () => this.createWeatherChannel());
    this.loadWeatherLocation();
    this.updateSourceControls();
  }

  async request(url, options = {}) {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...(this.identity?.csrf_token && !["GET", "HEAD"].includes((options.method || "GET").toUpperCase()) ? {"X-Analog-CSRF": this.identity.csrf_token} : {}),
        ...(options.headers || {}),
      },
      ...options,
      credentials: "same-origin",
      cache: "no-store",
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(
        body.detail || `Request failed: ${response.status}`,
      );
    }

    return response.status === 204 ? null : response.json();
  }


  updateSourceControls() {
    const isFolder = this.sourceType.value === "folder";
    const isYouTube = this.sourceType.value === "youtube";
    this.folderPickerButton.hidden = !isFolder;
    this.sourceInput.readOnly = isYouTube;
    this.sourceInput.placeholder = isFolder
      ? "/media/analog/cartoons"
      : isYouTube ? "Select YouTube subscriptions below"
      : this.sourceType.value === "pluto" ? "https://pluto.tv/… (official channel share link)"
      : "https://example.com/playlist.m3u8";
  }

  async selectFolder() {
    const status = document.querySelector("#channelStatus");
    status.textContent = "Opening folder picker…";

    try {
      const result = await this.request(
        "/api/channels/select-folder",
        { method: "POST" },
      );

      if (result.path) {
        this.sourceInput.value = result.path;
        status.textContent = "Folder selected.";
      } else {
        status.textContent = "Folder selection cancelled.";
      }
    } catch (error) {
      status.textContent = error.message;
    }
  }

  async loadChannels() {
    const channels = await this.request("/api/channels");
    const container = document.querySelector("#channels");

    container.innerHTML = channels.length
      ? ""
      : "<p>No channels configured.</p>";

    channels.forEach(channel => {
      container.appendChild(this.renderChannel(channel));
    });
  }

  renderChannel(channel) {
    const row = document.createElement("article");
    row.className = "channel-row";

    row.innerHTML = `
      <div class="channel-number">
        ${String(channel.number).padStart(2, "0")}
      </div>
      <div class="channel-copy">
        <strong>${this.escapeHtml(channel.name)}</strong>
        <small>
          ${this.escapeHtml(channel.source_type)}
          · ${channel.items.length} items
        </small>
        <code>${this.escapeHtml(channel.source)}</code>
      </div>
      <div class="channel-actions">
        <button data-action="scan">Scan</button>
        <button data-action="delete">Delete</button>
      </div>
    `;

    row.querySelector('[data-action="scan"]').onclick =
      async () => {
        await this.request(
          `/api/channels/${channel.id}/scan`,
          { method: "POST" },
        );
        await this.loadChannels();
      };

    row.querySelector('[data-action="delete"]').onclick =
      async () => {
        await this.request(
          `/api/channels/${channel.id}`,
          { method: "DELETE" },
        );
        await this.loadChannels();
      };

    return row;
  }

  async createChannel(event) {
    event.preventDefault();

    const status = document.querySelector("#channelStatus");
    const data = Object.fromEntries(
      new FormData(this.channelForm),
    );

    data.number = Number(data.number);
    data.enabled = true;

    try {
      const result = await this.request("/api/channels", {
        method: "POST",
        body: JSON.stringify(data),
      });

      status.textContent =
        `Added ${result.channels_created || 1} Analog TV channel${(result.channels_created || 1) === 1 ? "" : "s"}. Imported ${result.items_imported} stream${result.items_imported === 1 ? "" : "s"}.`;

      this.channelForm.reset();
      await this.loadChannels();
    } catch (error) {
      status.textContent = error.message;
    }
  }

  async createAlert(event) {
    event.preventDefault();

    const data = Object.fromEntries(
      new FormData(this.alertForm),
    );

    await this.request("/api/alerts", {
      method: "POST",
      body: JSON.stringify(data),
    });

    this.alertForm.reset();
  }

  async loadSettings() {
    const values = await this.request("/api/settings");

    for (const [key, value] of Object.entries(values)) {
      const input = this.settingsForm.elements[key] || this.broadcastSettingsForm?.elements[key] || this.youtubeSettingsForm?.elements[key];
      if (!input) continue;

      if (input.type === "checkbox") {
        input.checked = value === "true";
      } else if (key !== "telegram_token") {
        input.value = value;
      }
    }
  }

  async saveSettings(event) {
    event.preventDefault();

    const formData = new FormData(this.settingsForm);
    const data = Object.fromEntries(formData);

    data.telegram_enabled =
      formData.has("telegram_enabled");
    data.weather_refresh_minutes =
      Number(data.weather_refresh_minutes || 15);

    const status = document.querySelector("#settingsStatus");

    try {
      await this.request("/api/settings", {
        method: "PUT",
        body: JSON.stringify(data),
      });

      status.textContent =
        "Saved. Restart Analog TV to reload the Telegram worker.";
    } catch (error) {
      status.textContent = error.message;
    }
  }

  async saveExtraSettings(event, form, statusId) {
    event.preventDefault();
    const current = await this.request("/api/settings");
    const fd = new FormData(form);
    const data = {...current};
    for (const el of form.elements) {
      if (!el.name) continue;
      if (el.type === "checkbox") data[el.name] = el.checked;
      else if (el.type === "number") data[el.name] = Number(el.value);
      else data[el.name] = el.value;
    }
    // Restore secrets if blank: backend keeps existing secret values.
    await this.request("/api/settings", {method:"PUT", body:JSON.stringify(data)});
    document.querySelector(`#${statusId}`).textContent = "Saved.";
  }

  async testWeatherTicker() {
    const status=document.querySelector("#broadcastStatus");
    try {
      await this.request("/api/alerts/test-weather", {method:"POST"});
      status.textContent="Test weather ticker sent to the TV.";
    } catch(error) { status.textContent=error.message; }
  }

  async connectYouTube() {
    const status=document.querySelector("#youtubeStatus");
    try {
      const result=await this.request("/api/youtube/auth-url");
      window.location.href=result.url;
    } catch(error) { status.textContent=error.message; }
  }

  async loadYouTubeSubscriptions() {
    const status=document.querySelector("#youtubeStatus");
    try {
      const subs=await this.request("/api/youtube/subscriptions");
      const box=document.querySelector("#youtubeSubscriptions"); box.innerHTML="";
      subs.forEach(sub => {
        const label=document.createElement("label"); label.className="check subscription-row";
        label.innerHTML=`<input type="checkbox" value="${this.escapeHtml(sub.channel_id)}"><span>${this.escapeHtml(sub.title)}</span>`;
        label.querySelector("input").addEventListener("change", () => this.applyYouTubeSelection());
        box.appendChild(label);
      });
      status.textContent=`Loaded ${subs.length} subscriptions. Select creators, then add a YouTube channel above.`;
    } catch(error) { status.textContent=error.message; }
  }

  applyYouTubeSelection() {
    const ids=[...document.querySelectorAll("#youtubeSubscriptions input:checked")].map(x=>x.value);
    this.sourceInput.value=JSON.stringify(ids);
    if (ids.length) this.sourceType.value="youtube";
    this.updateSourceControls();
  }


  async loadWeatherLocation() {
    try {
      const result = await this.request("/api/weather/location");
      const area = result.location;
      if (area) this.showSelectedLocation(area);
    } catch (error) {
      document.querySelector("#weatherLocationStatus").textContent = error.message;
    }
  }

  showSelectedLocation(area) {
    this.pendingWeatherLocation = area;
    document.querySelector("#selectedWeatherLocation").textContent =
      `${area.city || "Selected area"}${area.country ? ", " + area.country : ""} | ${Number(area.latitude).toFixed(4)}, ${Number(area.longitude).toFixed(4)} | ${area.source || "manual"}`;
  }

  async searchLocation() {
    const status = document.querySelector("#weatherLocationStatus");
    const query = document.querySelector("#locationQuery").value.trim();
    const country = document.querySelector("#locationCountry").value.trim();
    if (!query) { status.textContent = "Enter a postal code or city."; return; }
    status.textContent = "Searching locations…";
    try {
      const result = await this.request(`/api/weather/search?query=${encodeURIComponent(query)}&country=${encodeURIComponent(country)}`);
      const list = document.querySelector("#locationResults");
      list.replaceChildren();
      for (const area of result.results || []) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `${area.city}, ${area.region || ""}, ${area.country || ""}`;
        button.addEventListener("click", () => this.saveWeatherLocation(area));
        list.appendChild(button);
      }
      status.textContent = result.results?.length ? "Select the correct location above." : "No matches found. Try a city name.";
    } catch (error) { status.textContent = error.message; }
  }

  async detectIpLocation() {
    const status = document.querySelector("#weatherLocationStatus");
    status.textContent = "Detecting approximate location using server public IP…";
    try {
      const area = await this.request("/api/weather/detect-ip");
      this.showSelectedLocation(area);
      const results = document.querySelector("#locationResults");
      results.replaceChildren();
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `CONFIRM ${area.city}, ${area.country} (APPROXIMATE)`;
      button.addEventListener("click", () => this.saveWeatherLocation(area));
      results.appendChild(button);
      status.textContent = "IP detection is approximate. Confirm the location or search your postal code instead.";
    } catch (error) { status.textContent = error.message; }
  }

  async saveWeatherLocation(area) {
    const status = document.querySelector("#weatherLocationStatus");
    try {
      const selected = await this.request("/api/weather/location", {
        method: "PUT",
        body: JSON.stringify({
          latitude: area.latitude, longitude: area.longitude,
          city: area.city, country: area.country || "", source: area.source || "manual",
        }),
      });
      this.showSelectedLocation(selected);
      document.querySelector("#locationResults").replaceChildren();
      status.textContent = "Weather location saved. Forecast will refresh hourly.";
    } catch (error) { status.textContent = error.message; }
  }

  async createWeatherChannel() {
    const status = document.querySelector("#weatherLocationStatus");
    if (!this.pendingWeatherLocation) { status.textContent = "Select and save a location first."; return; }
    try {
      const number = Number(document.querySelector("#weatherChannelNumber").value);
      const result = await this.request("/api/weather/channel", {
        method: "POST", body: JSON.stringify({number}),
      });
      await this.loadChannels();
      status.textContent = `Weather channel ${result.number} ${result.created ? "created" : "already exists"}.`;
    } catch (error) { status.textContent = error.message; }
  }

  escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
}

new AnalogTVAdmin().boot();
