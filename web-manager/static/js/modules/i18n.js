/* I18n helpers (lightweight, no dependencies) */

function formatTemplate(template, params) {
    if (!params) {
        return template;
    }
    return template.replace(/\{([^}]+)\}/g, function (match, key) {
        if (Object.prototype.hasOwnProperty.call(params, key)) {
            return String(params[key]);
        }
        return match;
    });
}

function resolveTranslation(key) {
    if (window.I18N_TRANSLATIONS && key in window.I18N_TRANSLATIONS) {
        return window.I18N_TRANSLATIONS[key];
    }
    if (window.I18N_FALLBACK && key in window.I18N_FALLBACK) {
        return window.I18N_FALLBACK[key];
    }
    return key;
}

function t(key, params) {
    if (!key) {
        return "";
    }
    const value = resolveTranslation(key);
    if (typeof value === "string") {
        return formatTemplate(value, params);
    }
    return String(value);
}

function setLanguage(lang) {
    if (!lang) {
        return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("lang", lang);
    window.location.href = url.toString();
}

window.t = t;
window.setLanguage = setLanguage;
