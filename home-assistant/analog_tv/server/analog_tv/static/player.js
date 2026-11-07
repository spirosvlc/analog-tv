console.info("Analog TV 1.0 | phosphor program guide + live weather");
class AnalogTVPlayer {
  constructor() {
    this.video = document.querySelector("#video");
    this.staticLayer = document.querySelector("#static");
    this.youtubeLayer = document.querySelector("#youtubeLayer");
    this.channelBug = document.querySelector("#channelBug");
    this.emptyState = document.querySelector("#emptyState");
    this.channelNumber = document.querySelector("#channelNumber");
    this.channelName = document.querySelector("#channelName");
    this.channelNumberEntry = document.querySelector("#channelNumberEntry");
    this.channelNumberEntryValue = document.querySelector("#channelNumberEntryValue");
    this.controlOsd = document.querySelector("#controlOsd");
    this.controlIcon = document.querySelector("#controlIcon");
    this.controlLabel = document.querySelector("#controlLabel");
    this.volumeMeterFill = document.querySelector("#volumeMeterFill");
    this.keyDebug = document.querySelector("#keyDebug");

    this.channels = [];
    this.currentChannelIndex = 0;
    this.currentItemIndex = 0;
    this.latestAlertId = 0;
    this.activeAlert = null;
    this.alertAudioContext = null;
    this.alertToneNodes = [];
    this.alertToneCloseTimer = null;
    this.hls = null;
    this.youtubePlayer = null;
    this.youtubeReady = false;
    this.currentMediaKind = "video";
    this.itemEndTimer = null;
    this.previousVolume = 1;
    this.hasUserInteraction = false;
    this.osdTimer = null;
    this.keyDebugTimer = null;
    this.channelEntryTimer = null;
    this.channelEntryBuffer = "";

    // Browsers permit reliable autoplay when media starts muted.
    this.video.muted = true;
    this.video.autoplay = true;

    this.guideElement = document.querySelector("#analogGuide");
    this.guideRows = document.querySelector("#guideRows");
    this.guideOpen = false;
    this.guideSelectedIndex = 0;
    this.weatherLayer = document.querySelector("#weatherChannel");
    this.plutoLayer = document.querySelector("#plutoChannel");
    this.weatherForecast = null;
    this.weatherSlideIndex = 0;
    this.weatherSlideTimer = null;
    this.weatherRefreshTimer = null;
    this.currentProgram = null;
    this.plutoUrl = null;
    this.lastGuideClockDate = null;
  }

  async boot() {
    this.channels = await this.request("/api/channels");

    if (!this.channels.length) {
      return;
    }

    this.emptyState.classList.add("hidden");
    this.bindEvents();
    this.refreshClock();
    window.setInterval(() => this.refreshClock(), 15000);
    window.setInterval(() => { if (this.guideOpen) this.renderGuide(); }, 60000);
    this.tune(0);

    window.setInterval(
      () => this.checkAlerts(),
      2000,
    );
  }

  bindEvents() {
    this.video.addEventListener(
      "ended",
      () => this.playNextItem(),
    );

    document.addEventListener(
      "keydown",
      event => this.handleKey(event),
    );
    document.querySelector("#plutoOpenButton")?.addEventListener("click", () => this.openPluto());
    // Clickable in ordinary browsers; Android's native touch layer lets guide touches through.
    this.guideRows?.addEventListener("click", (event) => {
      const row = event.target.closest("[data-index]");
      if (!row) return;
      const index = Number(row.dataset.index);
      if (index === this.guideSelectedIndex) this.watchSelectedGuideChannel();
      else this.selectGuideIndex(index);
    });
  }

  async request(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return response.status === 204 ? null : response.json();
  }

  handleKey(event) {
    this.registerUserInteraction();

    const key = event.key || "";
    const keyCode = event.keyCode || event.which || 0;

    const nextChannelKeys = new Set([
      "ArrowUp", "PageUp", "ChannelUp", "MediaTrackNext", "TVChannelUp",
    ]);
    const previousChannelKeys = new Set([
      "ArrowDown", "PageDown", "ChannelDown", "MediaTrackPrevious", "TVChannelDown",
    ]);
    const okKeys = new Set([
      "Enter", "Accept", "Select", "OK", "MediaPlayPause", "0",
    ]);
    const backKeys = new Set([
      "Escape", "Back", "BrowserBack", "GoBack", "Exit",
    ]);
    const volumeUpKeys = new Set([
      "ArrowRight", "AudioVolumeUp", "VolumeUp", "+", "=",
    ]);
    const volumeDownKeys = new Set([
      "ArrowLeft", "AudioVolumeDown", "VolumeDown", "-", "_",
    ]);
    const muteKeys = new Set([
      "AudioVolumeMute", "VolumeMute", "Mute", "m", "M",
    ]);

    const nextChannelCodes = new Set([33, 427]);
    const previousChannelCodes = new Set([34, 428]);
    const okCodes = new Set([13, 23, 48, 415]);
    const backCodes = new Set([27, 461, 10009]);
    const volumeUpCodes = new Set([175, 447]);
    const volumeDownCodes = new Set([174, 448]);
    const muteCodes = new Set([173, 449]);

    if (
      this.activeAlert &&
      (
        okKeys.has(key) ||
        backKeys.has(key) ||
        key === " " ||
        okCodes.has(keyCode) ||
        backCodes.has(keyCode)
      )
    ) {
      event.preventDefault();
      event.stopPropagation();
      this.dismissAlert();
      return;
    }

    if (this.guideOpen) {
      if (backKeys.has(key) || backCodes.has(keyCode)) {
        event.preventDefault(); this.closeGuide(); return;
      }
      if (okKeys.has(key) || okCodes.has(keyCode)) {
        event.preventDefault(); this.watchSelectedGuideChannel(); return;
      }
      if (nextChannelKeys.has(key) || nextChannelCodes.has(keyCode)) {
        event.preventDefault(); this.selectGuideIndex(this.guideSelectedIndex + 1); return;
      }
      if (previousChannelKeys.has(key) || previousChannelCodes.has(keyCode)) {
        event.preventDefault(); this.selectGuideIndex(this.guideSelectedIndex - 1); return;
      }
      if (key === "ArrowRight") {
        event.preventDefault(); this.selectGuideIndex(this.guideSelectedIndex + 5); return;
      }
      if (key === "ArrowLeft") {
        event.preventDefault(); this.selectGuideIndex(this.guideSelectedIndex - 5); return;
      }
    }

    // Preserve short 0 as OK, but allow entering channel 10/20/90/100.
    // The first digit (1-9) starts number entry; 0 only extends it.
    if (key === "0" && this.channelEntryBuffer) {
      event.preventDefault(); this.showChannelNumberEntry("0"); return;
    }

    if (okKeys.has(key) || okCodes.has(keyCode)) {
      event.preventDefault(); this.openGuide(); return;
    }
    if (backKeys.has(key) || backCodes.has(keyCode)) {
      event.preventDefault(); return;
    }

    if (/^[1-9]$/.test(key)) {
      event.preventDefault();
      event.stopPropagation();
      this.showChannelNumberEntry(key);
      return;
    }

    if (nextChannelKeys.has(key) || nextChannelCodes.has(keyCode)) {
      event.preventDefault();
      event.stopPropagation();
      this.tune(this.currentChannelIndex + 1);
      return;
    }

    if (previousChannelKeys.has(key) || previousChannelCodes.has(keyCode)) {
      event.preventDefault();
      event.stopPropagation();
      this.tune(this.currentChannelIndex - 1);
      return;
    }

    if (volumeUpKeys.has(key) || volumeUpCodes.has(keyCode)) {
      event.preventDefault();
      event.stopPropagation();
      this.changeVolume(0.1);
      return;
    }

    if (volumeDownKeys.has(key) || volumeDownCodes.has(keyCode)) {
      event.preventDefault();
      event.stopPropagation();
      this.changeVolume(-0.1);
      return;
    }

    if (muteKeys.has(key) || muteCodes.has(keyCode)) {
      event.preventDefault();
      event.stopPropagation();
      this.toggleMute();
      return;
    }

    if (key.toLowerCase() === "f") {
      document.documentElement.requestFullscreen?.();
      return;
    }

    this.showKeyDebug(event);
  }

  showChannelNumberEntry(digit) {
    window.clearTimeout(this.channelEntryTimer);

    this.channelEntryBuffer += digit;
    this.channelEntryBuffer = this.channelEntryBuffer.slice(-3);

    this.channelNumberEntryValue.textContent = this.channelEntryBuffer;
    this.channelNumberEntry.classList.remove("hidden");

    this.channelEntryTimer = window.setTimeout(() => {
      const requestedNumber = Number.parseInt(this.channelEntryBuffer, 10);
      const targetIndex = this.channels.findIndex(
        channel => channel.number === requestedNumber,
      );

      if (targetIndex >= 0) {
        this.tune(targetIndex);
      }

      this.channelEntryBuffer = "";
      this.channelNumberEntry.classList.add("hidden");
    }, 1400);
  }

  registerUserInteraction() {
    if (this.hasUserInteraction) {
      return;
    }

    this.hasUserInteraction = true;
    this.video.muted = false;

    if (this.video.paused) {
      this.safePlay();
    }
  }

  async safePlay() {
    try {
      await this.video.play();
      return true;
    } catch (error) {
      if (error?.name === "NotAllowedError") {
        // Retry muted. The first remote/key interaction will restore sound.
        this.video.muted = true;
        try {
          await this.video.play();
          return true;
        } catch (mutedError) {
          console.error("Muted autoplay failed:", mutedError);
        }
      } else if (error?.name !== "AbortError") {
        console.error("Video playback failed:", error);
      }
      return false;
    }
  }


  changeVolume(delta) {
    this.video.muted = false;
    this.video.volume = Math.min(1, Math.max(0, Number((this.video.volume + delta).toFixed(2))));
    if (this.currentMediaKind === "youtube" && this.youtubePlayer?.setVolume) {
      this.youtubePlayer.unMute(); this.youtubePlayer.setVolume(Math.round(this.video.volume*100));
    } else { this.safePlay(); }

    this.showControlOsd(
      delta > 0 ? "volume-up" : "volume-down",
      `VOLUME ${Math.round(this.video.volume * 100)}`,
      this.video.volume,
    );
  }

  toggleMute() {
    this.video.muted = !this.video.muted;
    if (this.currentMediaKind === "youtube" && this.youtubePlayer) {
      if (this.video.muted) this.youtubePlayer.mute(); else { this.youtubePlayer.unMute(); this.youtubePlayer.setVolume(Math.round(this.video.volume*100)); }
    } else if (!this.video.muted) { this.safePlay(); }

    this.showControlOsd(
      this.video.muted ? "mute" : "volume-up",
      this.video.muted
        ? "MUTE"
        : `VOLUME ${Math.round(this.video.volume * 100)}`,
      this.video.muted ? 0 : this.video.volume,
    );
  }

  showControlOsd(icon, label, level) {
    window.clearTimeout(this.osdTimer);

    const icons = {
      "volume-up": "◖)))",
      "volume-down": "◖))",
      mute: "◖×",
      ok: "✓",
    };

    this.controlIcon.textContent = icons[icon] || "◖";
    this.controlLabel.textContent = label;
    this.volumeMeterFill.style.width =
      `${Math.round(Math.max(0, Math.min(1, level)) * 100)}%`;

    this.controlOsd.classList.remove("hidden");
    this.osdTimer = window.setTimeout(
      () => this.controlOsd.classList.add("hidden"),
      2000,
    );
  }

  async tune(index) {
    this.currentChannelIndex =
      (index + this.channels.length) % this.channels.length;
    const channel = this.channels[this.currentChannelIndex];
    if (this.guideOpen) this.closeGuide();
    this.stopWeatherCycle();
    this.weatherLayer.classList.add("hidden");
    this.plutoLayer.classList.add("hidden");
    this.showStatic();
    if (channel.source_type === "weather") {
      this.stopPlayers();
      this.currentProgram = { title: "LOCAL WEATHER FORECAST", live: true };
      this.playWeatherChannel();
      return;
    }
    if (channel.source_type === "pluto") {
      this.stopPlayers();
      this.currentProgram = { title: "PLUTO TV / OFFICIAL STREAM", live: true };
      this.playPlutoChannel(channel);
      return;
    }
    this.channelNumber.textContent = String(channel.number).padStart(2, "0");
    this.channelName.textContent = channel.name;
    this.channelBug.classList.remove("hidden");
    window.setTimeout(() => this.channelBug.classList.add("hidden"), 2500);

    try {
      const now = await this.request(`/api/channels/${channel.id}/now`);
      this.currentProgram = now.item ? {
        title: now.item.title,
        live: now.live,
        offset_seconds: now.offset_seconds,
      } : { title: channel.name, live: true };
      await this.playNow(now);
    } catch (error) {
      console.error("Could not tune channel:", error);
    }
  }

  async playNow(now) {
    window.clearTimeout(this.itemEndTimer);
    if (!now.item) { this.stopPlayers(); return; }
    const item=now.item;
    if (item.media_kind === "youtube") {
      await this.playYouTube(item, now.offset_seconds || 0);
    } else {
      this.playVideoItem(item, now.offset_seconds || 0, now.live);
    }
    if (!now.live && item.duration_seconds > 0) {
      const remaining=Math.max(1,item.duration_seconds-(now.offset_seconds || 0));
      this.itemEndTimer=window.setTimeout(() => this.tune(this.currentChannelIndex), remaining*1000+500);
    }
  }

  refreshClock() {
    const current = new Date();
    const clock = document.querySelector("#guideClock");
    const date = document.querySelector("#guideDate");
    if (clock) clock.textContent = current.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    if (date) date.textContent = current.toLocaleDateString([], { weekday: "short", day: "2-digit", month: "short", year: "numeric" }).toUpperCase();
    const weatherClock = document.querySelector("#weatherLiveClock");
    if (weatherClock) weatherClock.textContent = current.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  }

  programSchedule(channel) {
    if (channel.source_type === "weather") return {
      now: "LOCAL WEATHER FORECAST", next: "HOURLY + 4-DAY OUTLOOK", nowTime: "LIVE", nextTime: "EVERY HOUR", progress: 0,
    };
    if (channel.source_type === "pluto") return {
      now: channel.name, next: "WATCH IN PLUTO TV", nowTime: "OFFICIAL", nextTime: "OPEN APP", progress: 0,
    };
    const items = (channel.items || []).filter(item => Number(item.duration_seconds) > 0);
    if (!items.length) return {
      now: channel.items?.[0]?.title || channel.name,
      next: "CONTINUOUS LIVE BROADCAST", nowTime: "LIVE", nextTime: "—", progress: 0,
    };
    const duration = items.reduce((total, item) => total + Number(item.duration_seconds), 0);
    // SQLAlchemy stores UTC timestamps without a timezone suffix. Interpret
    // those as UTC to match the backend's broadcast clock.
    const rawEpoch = channel.broadcast_epoch || "";
    const utcEpoch = rawEpoch && !/(Z|[+-]\d{2}:\d{2})$/.test(rawEpoch)
      ? `${rawEpoch}Z` : rawEpoch;
    const epoch = Date.parse(utcEpoch) || Date.now();
    const elapsed = (((Date.now() - epoch) / 1000) % duration) + duration;
    const phase = elapsed % duration;
    let offset = 0;
    for (let i = 0; i < items.length; i++) {
      const itemDuration = Number(items[i].duration_seconds);
      if (phase < offset + itemDuration || i === items.length - 1) {
        const into = Math.max(0, phase - offset);
        const remaining = itemDuration - into;
        const next = items[(i + 1) % items.length];
        const localTime = (time) => time.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",hour12:false});
        return {
          now: items[i].title,
          next: next.title,
          nowTime: localTime(new Date(Date.now() - into * 1000)),
          nextTime: localTime(new Date(Date.now() + remaining * 1000)),
          progress: Math.round(100 * into / itemDuration),
        };
      }
      offset += itemDuration;
    }
    return {now:channel.name,next:"CONTINUOUS BROADCAST",nowTime:"LIVE",nextTime:"—",progress:0};
  }

  openGuide() {
    if (!this.channels.length) return;
    this.guideOpen = true;
    this.guideSelectedIndex = this.currentChannelIndex;
    this.guideElement.classList.remove("hidden");
    document.querySelector("#tv").classList.add("guide-open");
    try { window.AnalogTVAndroid?.setGuideOpen?.(true); } catch (_) {}
    this.refreshClock();
    this.renderGuide();
  }

  closeGuide() {
    this.guideOpen = false;
    this.guideElement.classList.add("hidden");
    document.querySelector("#tv").classList.remove("guide-open");
    try { window.AnalogTVAndroid?.setGuideOpen?.(false); } catch (_) {}
  }

  renderGuide() {
    if (!this.guideOpen) return;
    this.guideRows.replaceChildren();
    const fragment = document.createDocumentFragment();
    this.channels.forEach((channel, index) => {
      const show = this.programSchedule(channel);
      const row = document.createElement("div");
      row.className = "guide-row" + (index === this.guideSelectedIndex ? " is-selected" : "");
      row.dataset.index = String(index);
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", String(index === this.guideSelectedIndex));
      // Avoid using innerHTML with M3U-supplied titles.
      const station = document.createElement("div"); station.className = "ch-cell";
      const no = document.createElement("strong"); no.className="ch-number"; no.textContent=String(channel.number).padStart(3,"0");
      const name = document.createElement("span"); name.className="ch-name"; name.textContent=channel.name;
      station.append(no,name);
      const now = this.createProgramCell(show.now, show.nowTime);
      const next = this.createProgramCell(show.next, show.nextTime);
      row.append(station,now,next);
      fragment.appendChild(row);
    });
    this.guideRows.appendChild(fragment);
    this.paintGuideSelection();
  }

  createProgramCell(title, time) {
    const cell=document.createElement("div"); cell.className="program-cell";
    const name=document.createElement("strong"); name.textContent=title;
    const when=document.createElement("small"); when.textContent=time;
    cell.append(name,when); return cell;
  }

  paintGuideSelection() {
    const channel=this.channels[this.guideSelectedIndex];
    if (!channel) return;
    const show=this.programSchedule(channel);
    document.querySelector("#guideChannelLabel").textContent = `CH ${String(channel.number).padStart(3,"0")} / ${channel.name.toUpperCase()}`;
    document.querySelector("#guideProgramTitle").textContent = show.now;
    document.querySelector("#guideProgramSubtitle").textContent = `${show.nowTime}  /  NEXT ${show.nextTime} — ${show.next}`;
    document.querySelector("#guideProgressFill").style.width = `${show.progress}%`;
    for (const row of this.guideRows.querySelectorAll(".guide-row")) {
      const selected=Number(row.dataset.index) === this.guideSelectedIndex;
      row.classList.toggle("is-selected",selected);
      row.setAttribute("aria-selected",String(selected));
    }
    const row=this.guideRows.querySelector(`[data-index="${this.guideSelectedIndex}"]`);
    row?.scrollIntoView({block:"nearest"});
  }

  selectGuideIndex(index) {
    this.guideSelectedIndex=(index+this.channels.length)%this.channels.length;
    this.paintGuideSelection();
  }

  watchSelectedGuideChannel() {
    const index=this.guideSelectedIndex;
    this.closeGuide();
    if (index !== this.currentChannelIndex) this.tune(index);
  }

  stopWeatherCycle() {
    clearInterval(this.weatherSlideTimer);
    clearInterval(this.weatherRefreshTimer);
    this.weatherSlideTimer=null;
    this.weatherRefreshTimer=null;
  }

  async playWeatherChannel() {
    this.weatherLayer.classList.remove("hidden");
    this.plutoLayer.classList.add("hidden");
    this.weatherSlideIndex=0;
    const reload=async () => {
      try {
        this.weatherForecast=await this.request("/api/weather/forecast");
        this.renderWeatherSlide();
      } catch (error) {
        document.querySelector("#weatherSlide").textContent=
          `WEATHER SIGNAL UNAVAILABLE / ${error.message}\nSET LOCATION IN ANALOG TV ADMIN`;
      }
    };
    await reload();
    this.weatherSlideTimer=setInterval(() => {
      this.weatherSlideIndex=(this.weatherSlideIndex+1)%3;
      this.renderWeatherSlide();
    },18000);
    this.weatherRefreshTimer=setInterval(reload,3600_000);
  }

  weatherDescription(code) {
    const c=Number(code);
    if (c === 0) return "CLEAR SKY";
    if (c <= 3) return "PARTLY CLOUDY";
    if ([45,48].includes(c)) return "FOG";
    if (c >= 51 && c <= 67) return "RAIN / DRIZZLE";
    if (c >= 71 && c <= 77) return "SNOW";
    if (c >= 80 && c <= 82) return "SHOWERS";
    if (c >= 95) return "THUNDERSTORM";
    return "VARIABLE CONDITIONS";
  }

  renderWeatherSlide() {
    const weather=this.weatherForecast;
    if (!weather || this.weatherLayer.classList.contains("hidden")) return;
    const slide=document.querySelector("#weatherSlide");
    slide.replaceChildren();
    const location=weather.location || {};
    document.querySelector("#weatherCity").textContent=`${location.city || "LOCAL"}${location.country ? ", "+location.country : ""}`.toUpperCase();
    const updated=new Date(weather.updated_at);
    document.querySelector("#weatherUpdated").textContent=`${weather.stale ? "CACHED DATA" : "UPDATED"} ${updated.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}  /  NEXT REFRESH +60 MIN`;
    const appendText=(tag,cls,text,parent=slide) => {
      const el=document.createElement(tag); el.className=cls; el.textContent=text; parent.appendChild(el);return el;
    };
    const current=weather.current || {};
    if (this.weatherSlideIndex === 0) {
      appendText("p","weather-kicker","ANALOG WEATHER / CURRENT CONDITIONS");
      appendText("h1","",(location.city || "LOCAL WEATHER").toUpperCase());
      const layout=document.createElement("div");layout.className="weather-current-grid";slide.appendChild(layout);
      appendText("div","weather-big-temp",`${Math.round(current.temperature_2m ?? 0)}°`,layout);
      const detail=document.createElement("div");detail.className="weather-current-detail";layout.appendChild(detail);
      appendText("div","",this.weatherDescription(current.weather_code),detail);
      appendText("div","",`FEELS LIKE ${Math.round(current.apparent_temperature ?? current.temperature_2m ?? 0)}°C`,detail);
      appendText("div","",`WIND ${Math.round(current.wind_speed_10m ?? 0)} KM/H`,detail);
      appendText("div","",`HUMIDITY ${Math.round(current.relative_humidity_2m ?? 0)}%`,detail);
      return;
    }
    if (this.weatherSlideIndex === 1) {
      appendText("p","weather-kicker","ANALOG WEATHER / THE NEXT 12 HOURS");
      appendText("h1","","HOURLY FORECAST");
      const grid=document.createElement("div");grid.className="forecast-strip";slide.appendChild(grid);
      const hours=weather.hourly || {};
      const dates=hours.time || [];
      const now=Date.now();
      let first=dates.findIndex(v => new Date(v).getTime() >= now - 3600_000);
      if (first < 0) first=0;
      for (let j=0;j<6;j++) {
        const i=Math.min(first+j*2, dates.length-1);
        if (i < 0) break;
        const cell=document.createElement("div");cell.className="forecast-cell";grid.appendChild(cell);
        appendText("small","",String(dates[i] || "").slice(11,16),cell);
        appendText("strong","",`${Math.round(hours.temperature_2m?.[i] ?? 0)}°`,cell);
        appendText("small","",this.weatherDescription(hours.weather_code?.[i]),cell);
        appendText("small","",`RAIN ${hours.precipitation_probability?.[i] ?? 0}%`,cell);
      }
      return;
    }
    appendText("p","weather-kicker","ANALOG WEATHER / FOUR-DAY OUTLOOK");
    appendText("h1","","THE NEXT FOUR DAYS");
    const grid=document.createElement("div");grid.className="forecast-day-strip";slide.appendChild(grid);
    const daily=weather.daily || {};
    for (let i=0;i<Math.min(4,(daily.time || []).length);i++) {
      const cell=document.createElement("div");cell.className="forecast-day";grid.appendChild(cell);
      appendText("small","",new Date(`${daily.time[i]}T12:00:00`).toLocaleDateString([], {weekday:"long",day:"numeric"}).toUpperCase(),cell);
      appendText("strong","",`${Math.round(daily.temperature_2m_max?.[i] ?? 0)}° / ${Math.round(daily.temperature_2m_min?.[i] ?? 0)}°`,cell);
      appendText("small","",this.weatherDescription(daily.weather_code?.[i]),cell);
      appendText("small","",`RAIN ${daily.precipitation_sum?.[i] ?? 0} MM`,cell);
    }
  }

  playPlutoChannel(channel) {
    this.plutoUrl=channel.source;
    this.plutoLayer.classList.remove("hidden");
    try { window.AnalogTVAndroid?.setExternalChannelVisible?.(true); } catch (_) {}
    document.querySelector("#plutoStationName").textContent=channel.name.toUpperCase();
  }

  openPluto() {
    if (!this.plutoUrl) return;
    if (!/^https:\/\/(www\.)?pluto\.tv\//.test(this.plutoUrl)) return;
    try {
      if (window.AnalogTVAndroid?.openExternal) {
        window.AnalogTVAndroid.openExternal(this.plutoUrl);
        return;
      }
    } catch (error) { console.warn(error); }
    window.open(this.plutoUrl,"_blank","noopener,noreferrer");
  }

  stopPlayers() {
    if (this.hls) { this.hls.destroy(); this.hls=null; }
    this.video.pause(); this.video.classList.add("hidden");
    this.youtubeLayer.classList.add("hidden");
    this.weatherLayer.classList.add("hidden");
    this.plutoLayer.classList.add("hidden");
    if (this.youtubePlayer?.stopVideo) this.youtubePlayer.stopVideo();
  }

  playVideoItem(item, offset=0, live=false) {
    this.currentMediaKind="video";
    if (this.youtubePlayer?.stopVideo) {
      try { this.youtubePlayer.stopVideo(); } catch (_) {}
    }
    this.youtubeLayer.classList.add("hidden");
    this.video.classList.remove("hidden");
    this.video.style.visibility = "visible";
    if (this.hls) { this.hls.destroy(); this.hls=null; }
    const afterReady=() => {
      if (!live && offset>0) { try { this.video.currentTime=offset; } catch(_){} }
      this.safePlay();
    };
    if (item.media_url.includes(".m3u8") && window.Hls?.isSupported()) {
      this.hls=new Hls({enableWorker:true,lowLatencyMode:true});
      this.hls.loadSource(item.media_url); this.hls.attachMedia(this.video);
      this.hls.on(Hls.Events.MANIFEST_PARSED, afterReady);
    } else {
      this.video.src=item.media_url; this.video.load();
      this.video.onloadedmetadata=afterReady;
    }
  }

  async ensureYouTubePlayer(videoId, offset) {
    for (let i=0;i<50 && !(window.YT && YT.Player);i++) await new Promise(r=>setTimeout(r,100));
    if (!(window.YT && YT.Player)) throw new Error("YouTube API did not load");
    if (!this.youtubePlayer) {
      this.youtubePlayer=new YT.Player("youtubePlayer", {
        width:"100%",height:"100%",videoId,
        playerVars:{autoplay:1,controls:0,disablekb:1,rel:0,playsinline:1,start:Math.floor(offset)},
        events:{onReady:(e)=>{this.youtubeReady=true;e.target.seekTo(offset,true);e.target.playVideo();},onStateChange:(e)=>{if(e.data===YT.PlayerState.ENDED)this.tune(this.currentChannelIndex);}}
      });
    } else {
      this.youtubePlayer.loadVideoById({videoId,startSeconds:offset});
    }
  }

  async playYouTube(item, offset=0) {
    this.currentMediaKind="youtube";
    if (this.hls) { this.hls.destroy(); this.hls=null; }
    this.video.pause();
    this.video.classList.add("hidden");
    this.youtubeLayer.classList.remove("hidden");
    await this.ensureYouTubePlayer(item.provider_id, offset);
  }

  showStatic(duration = 600) {
    this.staticLayer.classList.remove("hidden");
    window.setTimeout(
      () => this.staticLayer.classList.add("hidden"),
      duration,
    );
  }

  playNextItem() { this.tune(this.currentChannelIndex); }

  playCurrentItem() { this.tune(this.currentChannelIndex); }

  async checkAlerts() {
    const alert = await this.request(
      `/api/alerts/latest?after_id=${this.latestAlertId}`,
    );

    if (!alert) {
      return;
    }

    this.latestAlertId = alert.id;
    this.showAlert(alert);
  }

  showAlert(alert) {
    this.activeAlert = alert;

    const element = document.querySelector(
      `#${alert.level}Alert`,
    );
    const alertMessageElement = element.querySelector(".alert-message");
    const normalizedMessage = alert.level === "medium"
      ? alert.message.replace(/\s*\n+\s*/g, "  •  ").replace(/\s{2,}/g, " ").trim()
      : alert.message;
    alertMessageElement.textContent = normalizedMessage;
    element.classList.remove("hidden");

    if (alert.level === "critical") {
      this.previousVolume = this.video.volume;
      this.video.volume = Math.max(
        0.1,
        this.video.volume * 0.25,
      );
      this.playAlertTone();
    }

    if (alert.level === "medium") {
      const tickerWindow = element.querySelector(".ticker-window");
      const tickerText = element.querySelector(".ticker-text");

      // Analog TV retro crawl: no duration and no precomputed finish time.
      // Move the text at a fixed physical speed and dismiss only when the
      // rendered right edge of the text has actually left the ticker window.
      if (this.mediumTickerAnimation) {
        this.mediumTickerAnimation.cancel();
        this.mediumTickerAnimation = null;
      }
      if (this.mediumTickerRaf) {
        window.cancelAnimationFrame(this.mediumTickerRaf);
        this.mediumTickerRaf = null;
      }

      window.requestAnimationFrame(() => {
        const pixelsPerSecond = 58;
        const windowRect = tickerWindow.getBoundingClientRect();
        let x = tickerWindow.clientWidth + 24;
        let previousTimestamp = null;

        tickerText.style.transform = `translate3d(${x}px, 0, 0)`;

        const crawl = (timestamp) => {
          if (this.activeAlert?.id !== alert.id) {
            this.mediumTickerRaf = null;
            return;
          }

          if (previousTimestamp !== null) {
            const elapsedSeconds = Math.min(
              0.05,
              (timestamp - previousTimestamp) / 1000,
            );
            x -= pixelsPerSecond * elapsedSeconds;
            tickerText.style.transform = `translate3d(${x}px, 0, 0)`;
          }
          previousTimestamp = timestamp;

          const textRect = tickerText.getBoundingClientRect();

          // Only dismiss after the final character is completely past the
          // left boundary of the visible ticker area.
          if (textRect.right <= windowRect.left) {
            this.mediumTickerRaf = null;
            if (this.activeAlert?.id === alert.id) {
              this.dismissAlert();
            }
            return;
          }

          this.mediumTickerRaf = window.requestAnimationFrame(crawl);
        };

        this.mediumTickerRaf = window.requestAnimationFrame(crawl);
      });
    }
  }

  async dismissAlert() {
    if (!this.activeAlert) {
      return;
    }

    if (this.mediumTickerAnimation) {
      this.mediumTickerAnimation.cancel();
      this.mediumTickerAnimation = null;
    }
    if (this.mediumTickerRaf) {
      window.cancelAnimationFrame(this.mediumTickerRaf);
      this.mediumTickerRaf = null;
    }

    document
      .querySelectorAll(".alert")
      .forEach(element => element.classList.add("hidden"));

    this.stopAlertTone();

    // Dismissal is per player. The broadcast server keeps the alert in its
    // history; mutating shared alerts requires authenticated Broadcast Control.

    this.activeAlert = null;
    this.video.volume = this.previousVolume;
  }

  stopAlertTone() {
    if (this.alertToneCloseTimer) {
      window.clearTimeout(this.alertToneCloseTimer);
      this.alertToneCloseTimer = null;
    }

    for (const node of this.alertToneNodes) {
      try { node.oscillator.stop(); } catch (_) {}
      try { node.oscillator.disconnect(); } catch (_) {}
      try { node.gain.disconnect(); } catch (_) {}
    }
    this.alertToneNodes = [];

    if (this.alertAudioContext) {
      try { this.alertAudioContext.close(); } catch (_) {}
      this.alertAudioContext = null;
    }
  }

  playAlertTone() {
    this.stopAlertTone();

    const AudioContext =
      window.AudioContext || window.webkitAudioContext;
    const context = new AudioContext();
    this.alertAudioContext = context;

    const startTime = context.currentTime;
    const totalDuration = 10;
    const pulseDuration = 0.55;
    const gapDuration = 0.25;
    let cursor = 0;

    while (cursor < totalDuration) {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "square";
      oscillator.frequency.value = 853;
      gain.gain.setValueAtTime(0.08, startTime + cursor);
      gain.gain.setValueAtTime(0.08, startTime + cursor + pulseDuration - 0.02);
      gain.gain.linearRampToValueAtTime(0, startTime + cursor + pulseDuration);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(startTime + cursor);
      oscillator.stop(startTime + cursor + pulseDuration);
      this.alertToneNodes.push({ oscillator, gain });
      cursor += pulseDuration + gapDuration;
    }

    this.alertToneCloseTimer = window.setTimeout(() => {
      if (this.alertAudioContext === context) {
        this.stopAlertTone();
      }
    }, (totalDuration + 1) * 1000);
  }}

new AnalogTVPlayer().boot();
