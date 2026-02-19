"""
Générateur de rapport de diagnostic M&A — format Markdown.
"""

from __future__ import annotations

from datetime import date

from src.analyzer import CompanyAnalysis, analyze_consolidated
from src.extractor import CompanyData


def _fmt(value: float, unit: str = "€", decimals: int = 0) -> str:
    """Formate un nombre en milliers (K€) ou millions (M€)."""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M{unit}"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.{decimals}f}K{unit}"
    return f"{value:.{decimals}f}{unit}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _section(title: str, level: int = 2) -> str:
    return f"\n{'#' * level} {title}\n"


def _table_header(*cols: str) -> str:
    header = "| " + " | ".join(cols) + " |"
    separator = "| " + " | ".join(["---"] * len(cols)) + " |"
    return header + "\n" + separator


def _table_row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


# ---------------------------------------------------------------------------
# Sections du rapport
# ---------------------------------------------------------------------------

def _render_fiche_identite(company: CompanyData) -> str:
    fy = company.sorted_years[0] if company.sorted_years else None
    ca = _fmt(fy.chiffre_affaires) if fy else "N/D"
    rn = _fmt(fy.resultat_net) if fy else "N/D"
    return f"""
**Raison sociale** : {company.name}
**SIREN** : {company.siren}
**Forme juridique** : {company.legal_form}
**Adresse** : {company.address}
**Secteur** : {company.sector}
**Convention collective** : Boulangerie-pâtisserie artisanale (IDCC 843)
**Clôture** : {company.closing_date}
**Effectif** : {company.employees} salariés (dont apprentis)
**CA dernier exercice** : {ca}
**Résultat net dernier exercice** : {rn}
**Enseigne** : ANGE (2ème réseau boulangerie France, +250 unités)
"""


def _render_tableau_synoptique(company: CompanyData) -> str:
    years = company.sorted_years[:3]
    cols = ["Indicateur"] + [y.year for y in years]
    lines = [_table_header(*cols)]

    def row(label: str, values: list[float], formatter=_fmt) -> str:
        return _table_row(label, *[formatter(v) if v != 0 else "N/D" for v in values])

    lines.append(row("Chiffre d'affaires", [y.chiffre_affaires for y in years]))
    lines.append(row("Marge commerciale", [y.marge_commerciale for y in years]))
    lines.append(row("EBE (brut)", [y.ebe for y in years]))
    lines.append(row("Résultat d'exploitation", [y.resultat_exploitation for y in years]))
    lines.append(row("Résultat net", [y.resultat_net for y in years]))
    lines.append(row("Capitaux propres", [y.capitaux_propres for y in years]))
    lines.append(row("Dettes financières LT", [y.emprunts_lt for y in years]))
    lines.append(row("Total Bilan", [y.total_actif for y in years]))
    lines.append(row("Disponibilités", [y.disponibilites for y in years]))

    return "\n".join(lines)


def _render_valorisation(analysis: CompanyAnalysis) -> str:
    lines = []
    lines.append(f"**EBE normatif retenu** : {_fmt(analysis.ebitda_normalise)}")
    lines.append(f"**EBIT normatif** : {_fmt(analysis.ebit_normalise)}")
    lines.append(f"**Dette nette** : {_fmt(analysis.dette_nette)}")
    lines.append("")

    lines.append(_table_header("Méthode", "Bas", "Central", "Haut", "Notes"))
    for v in analysis.valuations:
        lines.append(_table_row(
            v.method,
            _fmt(v.low),
            _fmt(v.mid),
            _fmt(v.high),
            v.notes[:80] + "…" if len(v.notes) > 80 else v.notes,
        ))
    lines.append("")
    lines.append(
        f"**Fourchette retenue (pondérée 50/30/20)** : "
        f"{_fmt(analysis.valuations[0].low * 0.5 + analysis.valuations[1].low * 0.3 + analysis.valuations[2].low * 0.2)} "
        f"— {_fmt(analysis.valuations[0].high * 0.5 + analysis.valuations[1].high * 0.3 + analysis.valuations[2].high * 0.2)}"
    )
    lines.append(f"**Valeur d'Entreprise centrale retenue** : {_fmt(analysis.valeur_entreprise_retenue)}")
    lines.append(
        f"**→ Valeur des Titres** (VE − dette nette {_fmt(max(analysis.dette_nette, 0))}) : "
        f"**{_fmt(analysis.valeur_titres)}**"
    )
    return "\n".join(lines)


def _render_investment_case(analysis: CompanyAnalysis) -> str:
    lines = []

    lines.append("### ✅ Arguments « Bonne Affaire » (Pros)")
    for item in analysis.pros:
        lines.append(f"- {item}")

    lines.append("\n### ⚠️ Points de Vigilance / Risques (Cons)")
    for item in analysis.cons:
        lines.append(f"- {item}")

    return "\n".join(lines)


def _render_questions_vendeur(questions: list[str]) -> str:
    return "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))


def _render_leviers(leviers: list[str]) -> str:
    return "\n".join(f"- {l}" for l in leviers)


def _render_ratios(analysis: CompanyAnalysis) -> str:
    lines = [_table_header("Ratio", "Valeur", "Commentaire")]
    lines.append(_table_row(
        "Marge nette",
        _pct(analysis.ratio_marge_nette),
        "Bonne si > 5% en boulangerie franchise",
    ))
    lines.append(_table_row(
        "Marge EBE",
        _pct(analysis.ratio_marge_ebe),
        "Secteur : 8-14% attendu",
    ))
    lines.append(_table_row(
        "Levier (dette nette / EBE)",
        f"{analysis.ratio_endettement:.1f}x",
        "Acceptable si < 3x",
    ))
    lines.append(_table_row(
        "BFR",
        _fmt(analysis.bfr),
        f"{_fmt_ratio(analysis.bfr, analysis.company.sorted_years[0].chiffre_affaires):.1f}% du CA",
    ))
    lines.append(_table_row(
        "Rotation BFR",
        f"{analysis.rotation_bfr_jours:.0f} jours",
        "Négatif / faible = signe positif en boulangerie (vente au comptant)",
    ))
    return "\n".join(lines)


def _fmt_ratio(num: float, denom: float) -> float:
    if denom == 0:
        return 0.0
    return num / denom * 100


# ---------------------------------------------------------------------------
# Rapport consolidé
# ---------------------------------------------------------------------------

def generate_report(archange3: CompanyData, lavange: CompanyData) -> str:
    """
    Génère le rapport M&A complet au format Markdown.
    """
    results = analyze_consolidated(archange3, lavange)
    ana3 = results["archange3"]
    anal = results["lavange"]
    consol = results["consolide"]

    today = date.today().strftime("%d/%m/%Y")

    sections: list[str] = []

    # Titre
    sections.append(
        f"# Rapport de Diagnostic M&A — Mandat n°1326\n"
        f"**Cible** : SAS ARCH'ANGE3 & SAS LAVANGE (Franchises ANGE)  \n"
        f"**Date** : {today}  \n"
        f"**Conseiller** : Axe Avenir Conseil en Haut de Bilan (CNCEF n°05/917)  \n"
        f"**Confidentialité** : Document strictement confidentiel\n"
    )

    # ---- 1. FICHES D'IDENTITÉ ----
    sections.append(_section("1. Fiches d'Identité"))

    sections.append("### 1.1 SAS ARCH'ANGE3 — Cesson-Sévigné (35)")
    sections.append(_render_fiche_identite(archange3))

    sections.append("### 1.2 SAS LAVANGE — Laval (53)")
    sections.append(_render_fiche_identite(lavange))

    # ---- 2. TABLEAUX SYNOPTIQUES ----
    sections.append(_section("2. Tableaux Synoptiques Financiers (3 exercices)"))

    sections.append("### 2.1 SAS ARCH'ANGE3")
    sections.append(_render_tableau_synoptique(archange3))

    sections.append("\n### 2.2 SAS LAVANGE")
    sections.append(_render_tableau_synoptique(lavange))

    # ---- RATIOS ----
    sections.append(_section("3. Ratios Financiers Clés"))

    sections.append("### 3.1 SAS ARCH'ANGE3")
    sections.append(_render_ratios(ana3))

    sections.append("\n### 3.2 SAS LAVANGE")
    sections.append(_render_ratios(anal))

    # ---- 4. ANALYSE SECTORIELLE ET STRATÉGIQUE ----
    sections.append(_section("4. Contexte Sectoriel et Stratégique"))
    sections.append(
        """**Secteur** : Boulangerie-pâtisserie artisanale (NAF 10.71C) — marché estimé à **11 Md€** en France (2023).

**Tendances positives** :
- Résilience de la consommation de boulangerie (produit du quotidien, achats non-compressibles).
- Montée en gamme (bio, local, snacking premium) profitant au positionnement ANGE.
- Digitalisation de la distribution : click & collect, UberEats, Deliveroo → diversification du CA.
- Meilleure franchise alimentaire France 2023 (catégorie ANGE).

**Tendances négatives / risques** :
- Pression inflationniste sur les matières premières (blé, beurre, énergie) pesant sur les marges.
- Concurrence accrue des GMS (boulangeries industrielles), des chaînes (Paul, Marie Blachère).
- Difficultés de recrutement de boulangers qualifiés (pénurie nationale).
- Saturation possible du réseau ANGE dans certaines zones géographiques.

**Zone géographique** :
- **Cesson-Sévigné** (35) : commune dynamique de l'agglomération rennaise, fort pouvoir d'achat, croissance démographique soutenue.
- **Laval** (53) : préfecture de la Mayenne, bassin de chalandise plus limité (~50 000 hab. ville), mais peu de concurrents directs ANGE.

**Barrières à l'entrée** : coût d'investissement initial élevé (300-500K€), savoir-faire technique, exclusivité territoriale de franchise, durée d'apprentissage.
"""
    )

    # ---- 5. VALORISATION ----
    sections.append(_section("5. Analyse de Valorisation"))

    sections.append("### 5.1 SAS ARCH'ANGE3")
    sections.append(_render_valorisation(ana3))

    sections.append("\n### 5.2 SAS LAVANGE")
    sections.append(_render_valorisation(anal))

    sections.append("\n### 5.3 Vision Consolidée (Acquisition des 2 sites)")
    ca_total = consol["ca_total"]
    ebitda_total = consol["ebitda_total"]
    ve_low, ve_high = consol["ve_fourchette"]
    vt_low, vt_high = consol["valeur_titres_totale"]
    sections.append(
        f"| Indicateur consolidé | Valeur |\n"
        f"| --- | --- |\n"
        f"| CA total | {_fmt(ca_total)} |\n"
        f"| EBE normatif total | {_fmt(ebitda_total)} |\n"
        f"| VE fourchette | {_fmt(ve_low)} — {_fmt(ve_high)} |\n"
        f"| Valeur des Titres totale | **{_fmt(vt_low)} — {_fmt(vt_high)}** |\n"
    )
    sections.append(
        "\n> **Note** : L'acquisition simultanée des deux entités peut générer des synergies "
        "(mutualisation RH, achats groupés, management centralisé) estimées à +5-10% de l'EBE combiné. "
        "Cependant, elle double la dépendance à la franchise ANGE et l'exposition opérationnelle."
    )

    # ---- 6. DIAGNOSTIC D'INVESTISSEMENT ----
    sections.append(_section("6. Diagnostic d'Investissement (Investment Case)"))

    sections.append("### 6.1 SAS ARCH'ANGE3")
    sections.append(_render_investment_case(ana3))

    sections.append("\n### 6.2 SAS LAVANGE")
    sections.append(_render_investment_case(anal))

    # ---- 7. QUESTIONS AU VENDEUR ----
    sections.append(_section("7. Questions à Poser au Vendeur (Due Diligence)"))
    sections.append(_render_questions_vendeur(ana3.questions_vendeur))

    # ---- 8. LEVIERS DE NÉGOCIATION ----
    sections.append(_section("8. Leviers de Négociation pour l'Acheteur"))
    sections.append("*Objectif : obtenir le prix le plus bas possible tout en sécurisant l'opération.*\n")
    sections.append("**Applicables aux deux entités :**")
    sections.append(_render_leviers(ana3.leviers_negociation))

    # ---- 9. CONCLUSION STRATÉGIQUE ----
    sections.append(_section("9. Conclusion Stratégique"))
    vt3 = _fmt(ana3.valeur_titres)
    vtl = _fmt(anal.valeur_titres)
    sections.append(
        f"""### Avis d'ensemble

L'acquisition des franchises ANGE de Cesson-Sévigné et Laval constitue une **opportunité de marché
intéressante** dans un secteur résilient, portée par une enseigne bien positionnée.

**Points forts décisifs** : résultats positifs sur 3 exercices, CA en croissance à Laval, potentiel
de développement identifié, marque ANGE reconnue et primée.

**Points de vigilance** : baisse du CA et du résultat à Cesson en 2024, dépendance à la franchise,
sites uniques, besoin de capex de rénovation.

**Recommandation** :
- Procéder à une due diligence approfondie (audit comptable, juridique, social et fiscal).
- Négocier sur la base des leviers identifiés.
- Valorisation cible pour un acquéreur rationnel :
  - **ARCH'ANGE3** : {vt3} (valeur des titres, après dette nette)
  - **LAVANGE** : {vtl} (valeur des titres, après dette nette)
- Prévoir une garantie de passif de 18-24 mois couvrant a minima les risques fiscaux, sociaux
  et les risques liés au contrat de franchise.
- En cas d'acquisition simultanée, viser une valeur totale des titres inférieure à
  **{_fmt(vt_low)}** avec earn-out sur objectifs 2025-2026.

> *Ce rapport est établi sur la base des documents fournis. Les informations financières sont
> indicatives et devront être confirmées lors de la phase de due diligence. Tout investissement
> comporte des risques.*
"""
    )

    return "\n".join(sections)
