package gr.analogtv.client;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.URL;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public final class AnalogTVActivity extends Activity {

    private static final String PREFS_NAME = "analog_tv_settings";
    private static final String PREF_SERVER_URL = "server_url";

    private static final int ANALOG_GREEN = Color.rgb(125, 255, 101);
    private static final int ANALOG_GREEN_DIM = Color.rgb(34, 92, 30);
    private static final int ANALOG_GREEN_DARK = Color.rgb(0, 30, 0);

    private static final long RECONNECT_DELAY_MS = 5000L;
    private static final long RESUME_CHECK_DELAY_MS = 700L;
    private static final long LONG_PRESS_MS = 700L;

    private WebView webView;
    private StaticNoiseView staticView;
    private TextView statusView;
    private SharedPreferences preferences;
    private AlertDialog serverDialog;
    private AlertDialog maintenanceDialog;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService networkExecutor = Executors.newCachedThreadPool();

    private ConnectivityManager connectivityManager;
    private ConnectivityManager.NetworkCallback networkCallback;

    private boolean connected = false;
    private boolean networkAvailable = true;
    private boolean zeroLongPressTriggered = false;
    private boolean discoveryRunning = false;
    private String currentUrl = "";
    private volatile boolean guideVisible = false;
    private volatile boolean adminVisible = false;
    private volatile boolean externalChannelVisible = false;
    private static final long TOUCH_LONG_PRESS_MS = 700L;
    private float touchDownX;
    private float touchDownY;
    private boolean touchMoved = false;
    private boolean touchLongPressed = false;
    private static final float TOUCH_SLOP_DP = 32f;


    private final Runnable reconnectRunnable = new Runnable() {
        @Override
        public void run() {
            if (!networkAvailable || currentUrl == null || currentUrl.trim().isEmpty()) {
                return;
            }

            showStatic();
            showStatus("ANALOG TV // NO SIGNAL\nRETRYING…");
            webView.stopLoading();
            webView.loadUrl(currentUrl);
        }
    };

    private final Runnable touchLongPressRunnable = new Runnable() {
        @Override
        public void run() {
            touchLongPressed = true;
            showMaintenanceMenu();
        }
    };

    private final Runnable zeroLongPressRunnable = new Runnable() {
        @Override
        public void run() {
            zeroLongPressTriggered = true;
            showMaintenanceMenu();
        }
    };


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        preferences = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        connectivityManager =
            (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);

        createInterface();
        enterImmersiveMode();
        registerNetworkWatcher();

        String configuredUrl = preferences.getString(PREF_SERVER_URL, "");
        if (configuredUrl == null || configuredUrl.trim().isEmpty()) {
            showStatic();
            showStatus("ANALOG TV // SEARCHING\nSCANNING LOCAL NETWORK…");
            mainHandler.postDelayed(() -> discoverServers(true), 500L);
        } else {
            openAnalogServer(configuredUrl);
        }
    }

    private void createInterface() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        staticView = new StaticNoiseView(this);
        staticView.setVisibility(View.GONE);
        root.addView(staticView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.BLACK);
        webView.setFocusable(true);
        webView.setFocusableInTouchMode(true);
        configureWebView();
        root.addView(webView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));

        statusView = new TextView(this);
        statusView.setTextColor(ANALOG_GREEN);
        statusView.setBackgroundColor(Color.argb(225, 0, 20, 0));
        statusView.setTextSize(22);
        statusView.setGravity(Gravity.CENTER);
        statusView.setPadding(36, 24, 36, 24);
        statusView.setVisibility(View.GONE);
        root.addView(statusView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.CENTER
        ));


        setContentView(root);
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();

        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);

        webView.addJavascriptInterface(new AnalogTVBridge(), "AnalogTVAndroid");

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage message) {
                android.util.Log.d(
                    "ANALOG_WEB",
                    message.message()
                        + " @"
                        + message.lineNumber()
                        + ":"
                        + message.sourceId()
                );
                return true;
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                if (url == null || url.startsWith("about:")) {
                    return;
                }

                adminVisible = url.contains("/admin");
                guideVisible = false;
                externalChannelVisible = false;
                connected = true;
                cancelReconnect();
                hideStatus();
                hideStatic();
                view.requestFocus();
            }

            @Override
            public void onReceivedError(
                WebView view,
                WebResourceRequest request,
                WebResourceError error
            ) {
                if (request.isForMainFrame()) {
                    markDisconnected(
                        networkAvailable
                            ? "ANALOG TV // NO SIGNAL\nRETRYING…"
                            : "ANALOG TV // NETWORK OFFLINE"
                    );
                }
            }
        });
    }

    private void openAnalogServer(String enteredUrl) {
        String normalizedUrl = normalizeUrl(enteredUrl);
        currentUrl = normalizedUrl;

        preferences.edit()
            .putString(PREF_SERVER_URL, normalizedUrl)
            .apply();

        connected = false;
        cancelReconnect();
        showStatic();
        showStatus("ANALOG TV // CONNECTING…");
        webView.stopLoading();
        webView.loadUrl(normalizedUrl);
    }

    private String normalizeUrl(String enteredUrl) {
        String value = enteredUrl == null ? "" : enteredUrl.trim();

        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "http://" + value;
        }

        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }

        return value;
    }

    private void markDisconnected(String message) {
        connected = false;
        showStatic();
        showStatus(message);
        scheduleReconnect();
    }

    private void scheduleReconnect() {
        cancelReconnect();

        if (networkAvailable && currentUrl != null && !currentUrl.trim().isEmpty()) {
            mainHandler.postDelayed(reconnectRunnable, RECONNECT_DELAY_MS);
        }
    }

    private void cancelReconnect() {
        mainHandler.removeCallbacks(reconnectRunnable);
    }

    private void verifyAndRecover(String reason) {
        if (currentUrl == null || currentUrl.trim().isEmpty() || !networkAvailable) {
            return;
        }

        final String url = currentUrl;
        networkExecutor.execute(() -> {
            boolean reachable = probeAnalog(url, 1200);
            runOnUiThread(() -> {
                if (reachable) {
                    if (!connected) {
                        showStatus("ANALOG TV // SIGNAL RESTORED\nRECONNECTING…");
                        webView.stopLoading();
                        webView.loadUrl(url);
                    }
                } else {
                    connected = false;
                    showStatic();
                    showStatus("ANALOG TV // NO SIGNAL\nRETRYING…");
                    scheduleReconnect();
                }
            });
        });
    }

    private void registerNetworkWatcher() {
        if (connectivityManager == null) {
            return;
        }

        networkCallback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(Network network) {
                networkAvailable = true;
                runOnUiThread(() -> {
                    showStatus("ANALOG TV // NETWORK RESTORED\nRECONNECTING…");
                    mainHandler.postDelayed(
                        () -> verifyAndRecover("network available"),
                        400L
                    );
                });
            }

            @Override
            public void onLost(Network network) {
                networkAvailable = hasUsableNetwork();
                if (!networkAvailable) {
                    runOnUiThread(() -> {
                        connected = false;
                        cancelReconnect();
                        showStatic();
                        showStatus("ANALOG TV // NETWORK OFFLINE");
                    });
                }
            }

            @Override
            public void onCapabilitiesChanged(
                Network network,
                NetworkCapabilities capabilities
            ) {
                boolean usable =
                    capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
                networkAvailable = usable;

                if (usable && !connected) {
                    runOnUiThread(() ->
                        mainHandler.postDelayed(
                            () -> verifyAndRecover("network changed"),
                            350L
                        )
                    );
                }
            }
        };

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                connectivityManager.registerDefaultNetworkCallback(networkCallback);
            } else {
                NetworkRequest request = new NetworkRequest.Builder()
                    .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    .build();
                connectivityManager.registerNetworkCallback(request, networkCallback);
            }
        } catch (Exception ignored) {
            networkCallback = null;
        }

        networkAvailable = hasUsableNetwork();
    }

    private boolean hasUsableNetwork() {
        if (connectivityManager == null) {
            return true;
        }

        try {
            Network active = connectivityManager.getActiveNetwork();
            if (active == null) {
                return false;
            }

            NetworkCapabilities capabilities =
                connectivityManager.getNetworkCapabilities(active);

            return capabilities != null
                && capabilities.hasCapability(
                    NetworkCapabilities.NET_CAPABILITY_INTERNET
                );
        } catch (Exception ignored) {
            return true;
        }
    }

    private void showServerDialog(boolean mandatory) {
        if (serverDialog != null && serverDialog.isShowing()) {
            return;
        }

        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(
            preferences.getString(
                PREF_SERVER_URL,
                getString(R.string.default_analog_url)
            )
        );
        input.setSelectAllOnFocus(true);
        input.setTextSize(20);
        input.setTextColor(ANALOG_GREEN);
        input.setHintTextColor(ANALOG_GREEN_DIM);
        input.setBackgroundColor(ANALOG_GREEN_DARK);
        input.setPadding(18, 18, 18, 18);

        FrameLayout container = new FrameLayout(this);
        container.setPadding(24, 8, 24, 8);
        container.addView(input, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        serverDialog = new AlertDialog.Builder(this)
            .setTitle("ANALOG TV // SERVER")
            .setMessage(
                "Enter the Analog TV server address.\n"
                    + "Home Assistant example: http://192.168.1.45:8155"
            )
            .setView(container)
            .setPositiveButton("CONNECT", null)
            .setNeutralButton("DISCOVER", null)
            .setNegativeButton(
                mandatory ? "EXIT" : "CANCEL",
                (currentDialog, which) -> {
                    if (mandatory) {
                        finish();
                    }
                }
            )
            .create();

        serverDialog.setCanceledOnTouchOutside(false);
        serverDialog.setOnCancelListener(dialog -> {
            if (mandatory) {
                finish();
            }
        });

        serverDialog.setOnShowListener(ignored -> {
            tintDialogButtons(serverDialog);

            serverDialog.getButton(AlertDialog.BUTTON_POSITIVE)
                .setOnClickListener(view -> {
                    String value = input.getText().toString().trim();
                    if (value.isEmpty()) {
                        input.setError("Enter the ANALOG TV server address");
                        return;
                    }

                    serverDialog.dismiss();
                    serverDialog = null;
                    openAnalogServer(value);
                });

            serverDialog.getButton(AlertDialog.BUTTON_NEUTRAL)
                .setOnClickListener(view -> {
                    serverDialog.dismiss();
                    serverDialog = null;
                    discoverServers(mandatory);
                });
        });

        serverDialog.setOnDismissListener(dialog -> serverDialog = null);
        serverDialog.show();

        if (serverDialog.getWindow() != null) {
            serverDialog.getWindow().setSoftInputMode(
                WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
            );
        }

        input.requestFocus();
    }

    private void showMaintenanceMenu() {
        if (maintenanceDialog != null && maintenanceDialog.isShowing()) {
            return;
        }

        final String[] items = new String[] {
            "SERVER IP",
            "DISCOVER ANALOG SERVER",
            "RELOAD ANALOG TV",
            "CLEAR WEBVIEW CACHE",
            "RESTART CONNECTION",
            "SHOW APP VERSION",
            "SHOW SERVER REACHABILITY"
        };

        maintenanceDialog = new AlertDialog.Builder(this)
            .setTitle("ANALOG TV // SERVICE")
            .setItems(items, (dialog, which) -> {
                switch (which) {
                    case 0:
                        showServerDialog(false);
                        break;
                    case 1:
                        discoverServers(false);
                        break;
                    case 2:
                        reloadAnalog();
                        break;
                    case 3:
                        clearWebViewCache();
                        break;
                    case 4:
                        restartConnection();
                        break;
                    case 5:
                        showInfoDialog(
                            "ANALOG TV // VERSION",
                            "Android client " + getAppVersionName()
                        );
                        break;
                    case 6:
                        showReachability();
                        break;
                    default:
                        break;
                }
            })
            .setNegativeButton("CLOSE", null)
            .create();

        maintenanceDialog.setOnShowListener(ignored ->
            tintDialogButtons(maintenanceDialog)
        );
        maintenanceDialog.setOnDismissListener(dialog -> maintenanceDialog = null);
        maintenanceDialog.show();
    }

    private void tintDialogButtons(AlertDialog dialog) {
        if (dialog == null) {
            return;
        }

        if (dialog.getButton(AlertDialog.BUTTON_POSITIVE) != null) {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(ANALOG_GREEN);
        }
        if (dialog.getButton(AlertDialog.BUTTON_NEGATIVE) != null) {
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(ANALOG_GREEN);
        }
        if (dialog.getButton(AlertDialog.BUTTON_NEUTRAL) != null) {
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setTextColor(ANALOG_GREEN);
        }
    }

    private void showInfoDialog(String title, String message) {
        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton("OK", null)
            .create();

        dialog.setOnShowListener(ignored -> tintDialogButtons(dialog));
        dialog.show();
    }

    private void reloadAnalog() {
        if (webView == null || currentUrl == null || currentUrl.isEmpty()) {
            return;
        }

        showStatic();
        showStatus("ANALOG TV // RELOADING…");
        connected = false;
        webView.reload();
    }

    private void clearWebViewCache() {
        if (webView == null) {
            return;
        }

        webView.clearCache(true);
        webView.clearHistory();
        Toast.makeText(
            this,
            "ANALOG TV cache cleared",
            Toast.LENGTH_SHORT
        ).show();
    }

    private void restartConnection() {
        if (currentUrl == null || currentUrl.trim().isEmpty()) {
            showServerDialog(false);
            return;
        }

        connected = false;
        cancelReconnect();
        webView.stopLoading();
        webView.loadUrl("about:blank");
        showStatic();
        showStatus("ANALOG TV // RESTARTING CONNECTION…");

        mainHandler.postDelayed(
            () -> webView.loadUrl(currentUrl),
            450L
        );
    }

    private String getAppVersionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception ignored) {
            return "unknown";
        }
    }

    private void showReachability() {
        final String url = currentUrl;

        if (url == null || url.trim().isEmpty()) {
            showInfoDialog(
                "ANALOG TV // SIGNAL",
                "No Analog TV server configured."
            );
            return;
        }

        showStatus("ANALOG TV // CHECKING SIGNAL…");

        networkExecutor.execute(() -> {
            boolean reachable = probeAnalog(url, 1500);
            runOnUiThread(() -> {
                hideStatus();

                if (reachable) {
                    showInfoDialog(
                        "ANALOG TV // SIGNAL",
                        "SERVER ONLINE\n" + url
                    );
                } else {
                    showInfoDialog(
                        "ANALOG TV // SIGNAL",
                        "SERVER UNREACHABLE\n" + url
                    );
                }
            });
        });
    }

    private void discoverServers(boolean mandatoryIfNone) {
        if (discoveryRunning) {
            return;
        }

        discoveryRunning = true;
        showStatic();
        showStatus("ANALOG TV // SEARCHING\nSCANNING LOCAL NETWORK…");

        networkExecutor.execute(() -> {
            List<String> hosts = discoverAnalogOnLan();
            runOnUiThread(() -> {
                discoveryRunning = false;

                if (hosts.isEmpty()) {
                    showStatus("ANALOG TV // SEARCH COMPLETE\nNO SERVER FOUND");
                    mainHandler.postDelayed(() -> {
                        hideStatus();
                        showServerDialog(mandatoryIfNone);
                    }, 900L);
                    return;
                }

                if (hosts.size() == 1) {
                    showStatus("ANALOG TV // FOUND\n" + hosts.get(0));
                    mainHandler.postDelayed(
                        () -> openAnalogServer(hosts.get(0)),
                        550L
                    );
                    return;
                }

                showDiscoveredServers(hosts);
            });
        });
    }

    private void showDiscoveredServers(List<String> hosts) {
        String[] choices = hosts.toArray(new String[0]);

        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle("ANALOG TV // FOUND SERVERS")
            .setItems(choices, (d, which) -> openAnalogServer(choices[which]))
            .setNegativeButton("MANUAL", (d, which) -> showServerDialog(false))
            .create();

        dialog.setOnShowListener(ignored -> tintDialogButtons(dialog));
        dialog.show();
    }

    private List<String> discoverAnalogOnLan() {
        String prefix = localIpv4Prefix();
        if (prefix == null) {
            return Collections.emptyList();
        }

        Set<String> found = Collections.synchronizedSet(new LinkedHashSet<>());
        ExecutorService scanner = Executors.newFixedThreadPool(28);

        for (int host = 1; host <= 254; host++) {
            final int lastOctet = host;

            scanner.execute(() -> {
                String ip = prefix + lastOctet;

                if (probeAnalog("http://" + ip + ":8155", 280)) {
                    found.add("http://" + ip + ":8155");
                    return;
                }

                if (probeAnalog("http://" + ip + ":8080", 220)) {
                    found.add("http://" + ip + ":8080");
                }
            });
        }

        scanner.shutdown();

        try {
            scanner.awaitTermination(7, TimeUnit.SECONDS);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }

        List<String> result = new ArrayList<>(found);
        result.sort(Comparator.naturalOrder());
        return result;
    }

    private String localIpv4Prefix() {
        if (connectivityManager == null) {
            return null;
        }

        try {
            Network active = connectivityManager.getActiveNetwork();
            if (active == null) {
                return null;
            }

            LinkProperties properties =
                connectivityManager.getLinkProperties(active);

            if (properties == null) {
                return null;
            }

            for (LinkAddress address : properties.getLinkAddresses()) {
                InetAddress inetAddress = address.getAddress();

                if (inetAddress instanceof Inet4Address
                    && !inetAddress.isLoopbackAddress()) {
                    byte[] octets = inetAddress.getAddress();
                    return String.format(
                        Locale.US,
                        "%d.%d.%d.",
                        octets[0] & 0xff,
                        octets[1] & 0xff,
                        octets[2] & 0xff
                    );
                }
            }
        } catch (Exception ignored) {
        }

        return null;
    }

    private boolean probeAnalog(String baseUrl, int timeoutMs) {
        HttpURLConnection connection = null;

        try {
            String normalized = normalizeUrl(baseUrl);
            URL url = new URL(normalized + "/api/channels");

            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(timeoutMs);
            connection.setReadTimeout(timeoutMs);
            connection.setUseCaches(false);
            connection.setInstanceFollowRedirects(true);
            connection.setRequestProperty("Accept", "application/json");

            int status = connection.getResponseCode();
            return status >= 200 && status < 400;
        } catch (Exception ignored) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent event) {
        // Let HTML menus, Pluto launch buttons and Android dialogs receive real touches.
        if (guideVisible || adminVisible || externalChannelVisible ||
            (serverDialog != null && serverDialog.isShowing()) ||
            (maintenanceDialog != null && maintenanceDialog.isShowing())) {
            mainHandler.removeCallbacks(touchLongPressRunnable);
            return super.dispatchTouchEvent(event);
        }
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                touchDownX = event.getX();
                touchDownY = event.getY();
                touchMoved = false;
                touchLongPressed = false;
                mainHandler.postDelayed(touchLongPressRunnable, TOUCH_LONG_PRESS_MS);
                return true;
            case MotionEvent.ACTION_POINTER_DOWN:
                touchMoved = true;
                mainHandler.removeCallbacks(touchLongPressRunnable);
                return true;
            case MotionEvent.ACTION_MOVE:
                float maxMove = TOUCH_SLOP_DP * getResources().getDisplayMetrics().density;
                if (Math.abs(event.getX() - touchDownX) > maxMove ||
                    Math.abs(event.getY() - touchDownY) > maxMove) {
                    touchMoved = true;
                    mainHandler.removeCallbacks(touchLongPressRunnable);
                }
                return true;
            case MotionEvent.ACTION_UP:
                mainHandler.removeCallbacks(touchLongPressRunnable);
                if (!touchMoved && !touchLongPressed && connected) {
                    float width = getResources().getDisplayMetrics().widthPixels;
                    if (event.getX() < width * 0.30f) {
                        sendWebKey("ChannelDown", 428);
                    } else {
                        sendWebKey("ChannelUp", 427);
                    }
                }
                touchLongPressed = false;
                return true;
            case MotionEvent.ACTION_CANCEL:
                mainHandler.removeCallbacks(touchLongPressRunnable);
                touchLongPressed = false;
                touchMoved = false;
                return true;
            default:
                return super.dispatchTouchEvent(event);
        }
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        int keyCode = event.getKeyCode();

        if (serverDialog != null
            && serverDialog.isShowing()
            && keyCode == KeyEvent.KEYCODE_BACK
            && event.getAction() == KeyEvent.ACTION_DOWN) {
            View focused = serverDialog.getCurrentFocus();
            if (focused != null) {
                android.view.inputmethod.InputMethodManager imm =
                    (android.view.inputmethod.InputMethodManager)
                        getSystemService(INPUT_METHOD_SERVICE);
                imm.hideSoftInputFromWindow(focused.getWindowToken(), 0);
            }
            return true;
        }

        if (keyCode == KeyEvent.KEYCODE_0) {
            if (event.getAction() == KeyEvent.ACTION_DOWN) {
                if (event.getRepeatCount() == 0) {
                    zeroLongPressTriggered = false;
                    mainHandler.postDelayed(
                        zeroLongPressRunnable,
                        LONG_PRESS_MS
                    );
                }
                return true;
            }

            if (event.getAction() == KeyEvent.ACTION_UP) {
                mainHandler.removeCallbacks(zeroLongPressRunnable);

                if (!zeroLongPressTriggered) {
                    sendWebKey("0", 48);
                }

                zeroLongPressTriggered = false;
                return true;
            }
        }

        if (event.getAction() != KeyEvent.ACTION_DOWN) {
            return super.dispatchKeyEvent(event);
        }

        switch (keyCode) {
            case KeyEvent.KEYCODE_CHANNEL_UP:
            case KeyEvent.KEYCODE_PAGE_UP:
            case KeyEvent.KEYCODE_DPAD_UP:
                sendWebKey("ChannelUp", 427);
                return true;

            case KeyEvent.KEYCODE_CHANNEL_DOWN:
            case KeyEvent.KEYCODE_PAGE_DOWN:
            case KeyEvent.KEYCODE_DPAD_DOWN:
                sendWebKey("ChannelDown", 428);
                return true;

            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_NUMPAD_ENTER:
                sendWebKey("0", 48);
                return true;

            case KeyEvent.KEYCODE_1: sendWebKey("1", 49); return true;
            case KeyEvent.KEYCODE_2: sendWebKey("2", 50); return true;
            case KeyEvent.KEYCODE_3: sendWebKey("3", 51); return true;
            case KeyEvent.KEYCODE_4: sendWebKey("4", 52); return true;
            case KeyEvent.KEYCODE_5: sendWebKey("5", 53); return true;
            case KeyEvent.KEYCODE_6: sendWebKey("6", 54); return true;
            case KeyEvent.KEYCODE_7: sendWebKey("7", 55); return true;
            case KeyEvent.KEYCODE_8: sendWebKey("8", 56); return true;
            case KeyEvent.KEYCODE_9: sendWebKey("9", 57); return true;

            case KeyEvent.KEYCODE_VOLUME_UP:
                sendWebKey("AudioVolumeUp", 447);
                return true;

            case KeyEvent.KEYCODE_VOLUME_DOWN:
                sendWebKey("AudioVolumeDown", 448);
                return true;

            case KeyEvent.KEYCODE_VOLUME_MUTE:
            case KeyEvent.KEYCODE_MUTE:
                sendWebKey("AudioVolumeMute", 449);
                return true;

            case KeyEvent.KEYCODE_BACK:
                sendWebKey("BrowserBack", 10009);
                return true;

            case KeyEvent.KEYCODE_MENU:
            case KeyEvent.KEYCODE_SETTINGS:
                showMaintenanceMenu();
                return true;

            default:
                return super.dispatchKeyEvent(event);
        }
    }

    private void sendWebKey(String key, int keyCode) {
        if (webView == null || !connected) {
            return;
        }

        String escapedKey = key
            .replace("\\", "\\\\")
            .replace("'", "\\'");

        String javascript = String.format(
            Locale.US,
            "(function(){"
                + "const e=new KeyboardEvent('keydown',"
                + "{key:'%s',code:'%s',bubbles:true,cancelable:true});"
                + "Object.defineProperty(e,'keyCode',{get:function(){return %d;}});"
                + "Object.defineProperty(e,'which',{get:function(){return %d;}});"
                + "document.dispatchEvent(e);"
                + "})();",
            escapedKey,
            escapedKey,
            keyCode,
            keyCode
        );

        webView.evaluateJavascript(javascript, null);
    }

    private void showStatic() {
        runOnUiThread(() -> {
            if (staticView != null) {
                staticView.setVisibility(View.VISIBLE);
                staticView.startNoise();
            }
            if (webView != null) {
                webView.setVisibility(View.INVISIBLE);
            }
        });
    }

    private void hideStatic() {
        runOnUiThread(() -> {
            if (staticView != null) {
                staticView.stopNoise();
                staticView.setVisibility(View.GONE);
            }
            if (webView != null) {
                webView.setVisibility(View.VISIBLE);
            }
        });
    }

    private void showStatus(String message) {
        runOnUiThread(() -> {
            if (statusView != null) {
                statusView.setText(message);
                statusView.setVisibility(View.VISIBLE);
            }
        });
    }

    private void hideStatus() {
        runOnUiThread(() -> {
            if (statusView != null) {
                statusView.setVisibility(View.GONE);
            }
        });
    }



    private void enterImmersiveMode() {
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController controller = getWindow().getInsetsController();

            if (controller != null) {
                controller.hide(
                    WindowInsets.Type.statusBars()
                        | WindowInsets.Type.navigationBars()
                );
                controller.setSystemBarsBehavior(
                    WindowInsetsController
                        .BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                );
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            );
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);

        if (hasFocus) {
            enterImmersiveMode();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        enterImmersiveMode();

        if (webView != null) {
            webView.onResume();
            webView.resumeTimers();
        }

        if (currentUrl == null || currentUrl.trim().isEmpty()) {
            currentUrl = preferences.getString(PREF_SERVER_URL, "");
        }

        mainHandler.postDelayed(
            () -> verifyAndRecover("resume"),
            RESUME_CHECK_DELAY_MS
        );
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
            webView.pauseTimers();
        }

        super.onPause();
    }

    @Override
    protected void onDestroy() {
        cancelReconnect();
        mainHandler.removeCallbacks(zeroLongPressRunnable);
        mainHandler.removeCallbacks(touchLongPressRunnable);


        if (connectivityManager != null && networkCallback != null) {
            try {
                connectivityManager.unregisterNetworkCallback(networkCallback);
            } catch (Exception ignored) {
            }
        }

        networkExecutor.shutdownNow();

        if (webView != null) {
            webView.loadUrl("about:blank");
            webView.stopLoading();
            webView.setWebChromeClient(null);
            webView.setWebViewClient(null);
            webView.removeAllViews();
            webView.destroy();
            webView = null;
        }

        super.onDestroy();
    }

    private static final class StaticNoiseView extends View {
        private static final int NOISE_WIDTH = 160;
        private static final int NOISE_HEIGHT = 90;
        private static final long FRAME_MS = 80L;

        private final Bitmap bitmap;
        private final int[] pixels;
        private final Paint bitmapPaint = new Paint();
        private final Paint scanPaint = new Paint();
        private final Random random = new Random();

        private boolean running = false;
        private int jitterX = 0;
        private int jitterY = 0;

        private final Runnable frameRunnable = new Runnable() {
            @Override
            public void run() {
                if (!running) {
                    return;
                }

                generateFrame();
                invalidate();
                postDelayed(this, FRAME_MS);
            }
        };

        StaticNoiseView(Context context) {
            super(context);
            setBackgroundColor(Color.BLACK);

            bitmap = Bitmap.createBitmap(
                NOISE_WIDTH,
                NOISE_HEIGHT,
                Bitmap.Config.ARGB_8888
            );
            pixels = new int[NOISE_WIDTH * NOISE_HEIGHT];

            bitmapPaint.setFilterBitmap(false);
            scanPaint.setColor(Color.argb(65, 0, 0, 0));
            scanPaint.setStrokeWidth(1f);

            generateFrame();
        }

        void startNoise() {
            if (running) {
                return;
            }

            running = true;
            removeCallbacks(frameRunnable);
            post(frameRunnable);
        }

        void stopNoise() {
            running = false;
            removeCallbacks(frameRunnable);
        }

        private void generateFrame() {
            for (int i = 0; i < pixels.length; i++) {
                int sample = random.nextInt(100);
                int value;

                if (sample < 44) {
                    value = 0;
                } else if (sample < 72) {
                    value = 255;
                } else if (sample < 88) {
                    value = 175;
                } else {
                    value = 45;
                }

                pixels[i] = Color.rgb(value, value, value);
            }

            bitmap.setPixels(
                pixels,
                0,
                NOISE_WIDTH,
                0,
                0,
                NOISE_WIDTH,
                NOISE_HEIGHT
            );

            jitterX = random.nextInt(9) - 4;
            jitterY = random.nextInt(7) - 3;
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);

            if (getWidth() <= 0 || getHeight() <= 0) {
                return;
            }

            canvas.save();
            canvas.translate(jitterX, jitterY);

            android.graphics.Rect src = new android.graphics.Rect(
                0,
                0,
                NOISE_WIDTH,
                NOISE_HEIGHT
            );

            android.graphics.Rect dst = new android.graphics.Rect(
                -8,
                -8,
                getWidth() + 8,
                getHeight() + 8
            );

            canvas.drawBitmap(bitmap, src, dst, bitmapPaint);

            for (int y = 1; y < getHeight(); y += 4) {
                canvas.drawLine(0, y, getWidth(), y, scanPaint);
            }

            canvas.restore();
        }

        @Override
        protected void onDetachedFromWindow() {
            stopNoise();
            super.onDetachedFromWindow();
        }
    }

    public final class AnalogTVBridge {
        @JavascriptInterface
        public void setGuideOpen(boolean visible) {
            guideVisible = visible;
        }

        @JavascriptInterface
        public void setExternalChannelVisible(boolean visible) {
            externalChannelVisible = visible;
        }

        @JavascriptInterface
        public void openExternal(String uri) {
            try {
                Uri target = Uri.parse(uri);
                String host = target.getHost();
                if (!"https".equalsIgnoreCase(target.getScheme()) ||
                    !("pluto.tv".equalsIgnoreCase(host) ||
                      "www.pluto.tv".equalsIgnoreCase(host))) {
                    return;
                }
                runOnUiThread(() -> {
                    try {
                        Intent intent = new Intent(Intent.ACTION_VIEW, target);
                        startActivity(intent);
                    } catch (Exception ignored) {
                        Toast.makeText(AnalogTVActivity.this,
                            "Install the official Pluto TV app or use the website",
                            Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception ignored) {}
        }

        @JavascriptInterface
        public void openSettings() {
            runOnUiThread(() -> showMaintenanceMenu());
        }

        @JavascriptInterface
        public void showToast(String message) {
            runOnUiThread(() ->
                Toast.makeText(
                    AnalogTVActivity.this,
                    message,
                    Toast.LENGTH_SHORT
                ).show()
            );
        }
    }
}
