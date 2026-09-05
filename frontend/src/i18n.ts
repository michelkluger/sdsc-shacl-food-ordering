/**
 * UI chrome strings, in the four Swiss national languages plus English.
 *
 * Deliberately small. Everything a user reads *about a dish* - field labels, option names,
 * descriptions, validation messages - comes from the server, generated from the SHACL corpus.
 * What lives here is only the shell: buttons, headings, the empty state. Duplicating dish
 * vocabulary into the client would recreate exactly the coupling this project exists to avoid.
 *
 * The language list is not hardcoded against the backend's: the form response advertises
 * `availableLanguages`, and the switcher renders that. This table is the fallback for the
 * moment before the first response arrives.
 */

export const LANGUAGES = ['en', 'de', 'fr', 'it', 'rm'] as const

export type Language = (typeof LANGUAGES)[number]

export const DEFAULT_LANGUAGE: Language = 'en'

/** Endonyms: a language is named in itself, which is how a switcher stays usable. */
export const LANGUAGE_NAMES: Record<Language, string> = {
  en: 'English',
  de: 'Deutsch',
  fr: 'Français',
  it: 'Italiano',
  rm: 'Rumantsch',
}

export const LANGUAGE_SHORT: Record<Language, string> = {
  en: 'EN',
  de: 'DE',
  fr: 'FR',
  it: 'IT',
  rm: 'RM',
}

interface Strings {
  appTitle: string
  appLead: string
  chooseDish: string
  loadingMenu: string
  loadingForm: string
  menuFailed: string
  apiUnreachable: string
  formFailed: string
  placeOrder: string
  checking: string
  orderAccepted: string
  orderAnother: string
  reference: string
  problemsOne: string
  problemsMany: string
  problemsShort: string
  from: string
  contains: string
  estimatedTotal: string
  generatedFrom: string
  validatedOnServer: string
  required: string
  optional: string
  selectAll: string
  clear: string
  now: string
  yourOrder: string
  included: string
  priceEstimate: string
  chosenOf: string
  noneChosen: string
  languageLabel: string
  themeLabel: string
  themeSystem: string
  themeLight: string
  themeDark: string
  searchPlaceholder: string
  /** `{n}` is replaced with the count. */
  atMost: string
  atLeast: string
}

const en: Strings = {
  appTitle: 'Order food',
  appLead:
    'Every field below is generated on the server from a SHACL shape. This page holds no form definitions and no dish-specific logic.',
  chooseDish: 'Choose a dish',
  loadingMenu: 'Loading the menu…',
  loadingForm: 'Loading the form…',
  menuFailed: 'Could not load the menu',
  apiUnreachable: 'The API is not reachable. Is the backend running?',
  formFailed: 'Could not load the form',
  placeOrder: 'Place order',
  checking: 'Checking…',
  orderAccepted: 'Order accepted',
  orderAnother: 'Order another',
  reference: 'Reference',
  problemsOne: 'One thing needs fixing',
  problemsMany: '{n} things need fixing',
  problemsShort: '{n} to fix',
  from: 'From',
  contains: 'Contains',
  estimatedTotal: 'Estimated total',
  generatedFrom: 'Generated from',
  validatedOnServer: 'Validated on the server against that SHACL shape.',
  required: 'required',
  optional: 'optional',
  selectAll: 'Select all',
  clear: 'Clear',
  now: 'Now',
  yourOrder: 'Your order',
  included: 'included',
  priceEstimate: 'Estimate. The kitchen confirms the final price when the order is accepted.',
  chosenOf: '{n} of {max} chosen',
  noneChosen: 'None chosen',
  languageLabel: 'Language',
  themeLabel: 'Appearance',
  themeSystem: 'Match system',
  themeLight: 'Light',
  themeDark: 'Dark',
  searchPlaceholder: 'Search dishes…',
  atMost: 'at most {n}',
  atLeast: 'at least {n}',
}

const de: Strings = {
  appTitle: 'Essen bestellen',
  appLead:
    'Jedes Feld unten wird auf dem Server aus einer SHACL-Shape erzeugt. Diese Seite enthält keine Formulardefinitionen und keine gerichtspezifische Logik.',
  chooseDish: 'Gericht wählen',
  loadingMenu: 'Menü wird geladen…',
  loadingForm: 'Formular wird geladen…',
  menuFailed: 'Menü konnte nicht geladen werden',
  apiUnreachable: 'Die API ist nicht erreichbar. Läuft das Backend?',
  formFailed: 'Formular konnte nicht geladen werden',
  placeOrder: 'Bestellen',
  checking: 'Wird geprüft…',
  orderAccepted: 'Bestellung angenommen',
  orderAnother: 'Nochmals bestellen',
  reference: 'Referenz',
  problemsOne: 'Eine Sache muss noch korrigiert werden',
  problemsMany: '{n} Dinge müssen noch korrigiert werden',
  problemsShort: '{n} zu korrigieren',
  from: 'Ab',
  contains: 'Enthält',
  estimatedTotal: 'Geschätztes Total',
  generatedFrom: 'Erzeugt aus',
  validatedOnServer: 'Auf dem Server gegen diese SHACL-Shape validiert.',
  required: 'erforderlich',
  optional: 'optional',
  selectAll: 'Alle wählen',
  clear: 'Leeren',
  now: 'Jetzt',
  yourOrder: 'Deine Bestellung',
  included: 'inbegriffen',
  priceEstimate: 'Schätzung. Der endgültige Preis wird bei der Annahme der Bestellung bestätigt.',
  chosenOf: '{n} von {max} gewählt',
  noneChosen: 'Nichts gewählt',
  languageLabel: 'Sprache',
  themeLabel: 'Darstellung',
  themeSystem: 'Wie das System',
  themeLight: 'Hell',
  themeDark: 'Dunkel',
  searchPlaceholder: 'Gerichte suchen…',
  atMost: 'höchstens {n}',
  atLeast: 'mindestens {n}',
}

const fr: Strings = {
  appTitle: 'Commander à manger',
  appLead:
    "Chaque champ ci-dessous est généré sur le serveur à partir d'une forme SHACL. Cette page ne contient aucune définition de formulaire ni logique propre à un plat.",
  chooseDish: 'Choisir un plat',
  loadingMenu: 'Chargement du menu…',
  loadingForm: 'Chargement du formulaire…',
  menuFailed: 'Impossible de charger le menu',
  apiUnreachable: "L'API est injoignable. Le backend tourne-t-il ?",
  formFailed: 'Impossible de charger le formulaire',
  placeOrder: 'Commander',
  checking: 'Vérification…',
  orderAccepted: 'Commande acceptée',
  orderAnother: 'Commander à nouveau',
  reference: 'Référence',
  problemsOne: 'Un point à corriger',
  problemsMany: '{n} points à corriger',
  problemsShort: '{n} à corriger',
  from: 'Dès',
  contains: 'Contient',
  estimatedTotal: 'Total estimé',
  generatedFrom: 'Généré à partir de',
  validatedOnServer: 'Validé sur le serveur contre cette forme SHACL.',
  required: 'obligatoire',
  optional: 'facultatif',
  selectAll: 'Tout sélectionner',
  clear: 'Effacer',
  now: 'Maintenant',
  yourOrder: 'Votre commande',
  included: 'inclus',
  priceEstimate: "Estimation. Le prix définitif est confirmé à l'acceptation de la commande.",
  chosenOf: '{n} sur {max} choisis',
  noneChosen: 'Aucun choix',
  languageLabel: 'Langue',
  themeLabel: 'Apparence',
  themeSystem: 'Comme le système',
  themeLight: 'Clair',
  themeDark: 'Sombre',
  searchPlaceholder: 'Rechercher des plats…',
  atMost: 'au maximum {n}',
  atLeast: 'au minimum {n}',
}

const it: Strings = {
  appTitle: 'Ordina da mangiare',
  appLead:
    'Ogni campo qui sotto è generato sul server a partire da una forma SHACL. Questa pagina non contiene definizioni di modulo né logica specifica per piatto.',
  chooseDish: 'Scegli un piatto',
  loadingMenu: 'Caricamento del menu…',
  loadingForm: 'Caricamento del modulo…',
  menuFailed: 'Impossibile caricare il menu',
  apiUnreachable: 'API non raggiungibile. Il backend è in esecuzione?',
  formFailed: 'Impossibile caricare il modulo',
  placeOrder: 'Ordina',
  checking: 'Verifica…',
  orderAccepted: 'Ordine accettato',
  orderAnother: 'Ordina di nuovo',
  reference: 'Riferimento',
  problemsOne: 'Una cosa da correggere',
  problemsMany: '{n} cose da correggere',
  problemsShort: '{n} da correggere',
  from: 'Da',
  contains: 'Contiene',
  estimatedTotal: 'Totale stimato',
  generatedFrom: 'Generato da',
  validatedOnServer: 'Validato sul server contro questa forma SHACL.',
  required: 'obbligatorio',
  optional: 'facoltativo',
  selectAll: 'Seleziona tutto',
  clear: 'Cancella',
  now: 'Adesso',
  yourOrder: 'Il tuo ordine',
  included: 'incluso',
  priceEstimate: "Stima. Il prezzo definitivo viene confermato all'accettazione dell'ordine.",
  chosenOf: '{n} di {max} scelti',
  noneChosen: 'Nessuna scelta',
  languageLabel: 'Lingua',
  themeLabel: 'Aspetto',
  themeSystem: 'Come il sistema',
  themeLight: 'Chiaro',
  themeDark: 'Scuro',
  searchPlaceholder: 'Cerca piatti…',
  atMost: 'al massimo {n}',
  atLeast: 'almeno {n}',
}

const rm: Strings = {
  appTitle: 'Ordinar da mangiar',
  appLead:
    'Mintga champ sutvart vegn generà sin il server a partir dad ina furma SHACL. Questa pagina na cuntegna naginas definiziuns da formular ni logica specifica per in plat.',
  chooseDish: 'Tscherner in plat',
  loadingMenu: 'Chargiar il menu…',
  loadingForm: 'Chargiar il formular…',
  menuFailed: 'Betg pussaivel da chargiar il menu',
  apiUnreachable: "L'API n'è betg accessibla. Va il backend?",
  formFailed: 'Betg pussaivel da chargiar il formular',
  placeOrder: 'Ordinar',
  checking: 'Controlla…',
  orderAccepted: 'Orden acceptà',
  orderAnother: 'Ordinar danovamain',
  reference: 'Referenza',
  problemsOne: 'Ina chaussa sto vegnir currigida',
  problemsMany: '{n} chaussas ston vegnir currigidas',
  problemsShort: '{n} da currigir',
  from: 'Da',
  contains: 'Cuntegna',
  estimatedTotal: 'Total estimà',
  generatedFrom: 'Generà da',
  validatedOnServer: 'Validà sin il server cunter questa furma SHACL.',
  required: 'obligatoric',
  optional: 'facultativ',
  selectAll: 'Tscherner tut',
  clear: 'Stizzar',
  now: 'Ussa',
  yourOrder: 'Tes orden',
  included: 'incluis',
  priceEstimate: "Stimaziun. Il pretsch definitiv vegn confermà cun l'acceptaziun da l'orden.",
  chosenOf: '{n} da {max} tschernids',
  noneChosen: 'Nagut tschernì',
  languageLabel: 'Lingua',
  themeLabel: 'Apparientscha',
  themeSystem: 'Sco il sistem',
  themeLight: 'Cler',
  themeDark: 'Stgir',
  searchPlaceholder: 'Tschertgar plats…',
  atMost: 'maximalmain {n}',
  atLeast: 'almain {n}',
}

const TABLES: Record<Language, Strings> = { en, de, fr, it, rm }

export type Translate = (key: keyof Strings, values?: Record<string, string | number>) => string

/** Build a translate function for one language. Falls back to English key by key. */
export function translator(language: string): Translate {
  const table = TABLES[language as Language] ?? TABLES[DEFAULT_LANGUAGE]

  return (key, values) => {
    const template = table[key] || TABLES[DEFAULT_LANGUAGE][key]
    if (!values) return template
    return Object.entries(values).reduce(
      (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
      template,
    )
  }
}

export function isLanguage(value: string): value is Language {
  return (LANGUAGES as readonly string[]).includes(value)
}

const STORAGE_KEY = 'food-api.language'

/**
 * The language to start in: a previous explicit choice, else the browser's preference, else
 * English. Storage access is wrapped because it throws outright in some privacy modes.
 */
export function initialLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && isLanguage(stored)) return stored
  } catch {
    // Private browsing, blocked site data. Fall through to the browser preference.
  }

  for (const tag of navigator.languages ?? [navigator.language]) {
    const base = tag?.split('-')[0]?.toLowerCase()
    if (base && isLanguage(base)) return base
  }
  return DEFAULT_LANGUAGE
}

export function rememberLanguage(language: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // A remembered preference is a convenience, never a requirement.
  }
}
