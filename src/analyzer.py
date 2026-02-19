"""
Moteur d'analyse financière M&A pour le diagnostic des entreprises ANGE.
Implémente : ratios financiers, valorisation (multiples EBE, DCF, patrimoniale),
analyse de la dette nette, et diagnostic d'investissement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.extractor import CompanyData, FinancialYear


# ---------------------------------------------------------------------------
# Résultats d'analyse
# ---------------------------------------------------------------------------

@dataclass
class ValuationRange:
    low: float
    mid: float
    high: float
    method: str
    notes: str = ""

    def __str__(self) -> str:
        return (
            f"{self.method} : {self.low/1000:.0f}K€ – {self.high/1000:.0f}K€"
            f" (central {self.mid/1000:.0f}K€)"
        )


@dataclass
class CompanyAnalysis:
    company: CompanyData
    ebitda_normalise: float = 0.0
    ebit_normalise: float = 0.0
    dette_nette: float = 0.0
    bfr: float = 0.0
    tresorerie_nette: float = 0.0
    # Ratios
    ratio_endettement: float = 0.0      # dette nette / EBITDA
    ratio_marge_nette: float = 0.0
    ratio_marge_ebe: float = 0.0
    rotation_bfr_jours: float = 0.0
    # Valorisations
    valuations: list[ValuationRange] = field(default_factory=list)
    valeur_entreprise_retenue: float = 0.0
    valeur_titres: float = 0.0          # VE - dette nette
    # Qualitatif
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    questions_vendeur: list[str] = field(default_factory=list)
    leviers_negociation: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constantes sectorielles (boulangerie franchise France, 2024)
# ---------------------------------------------------------------------------

MULTIPLE_EBE_LOW = 3.0
MULTIPLE_EBE_MID = 4.0
MULTIPLE_EBE_HIGH = 5.5

WACC = 0.12          # Taux d'actualisation DCF (PME boulangerie, risque élevé)
GROWTH_TERMINAL = 0.015   # Taux de croissance terminal
DCF_YEARS = 5

# Ratio de dépréciation heuristique pour reconstruire l'EBE quand les dotations ne sont pas extraites
# (estimé à ~40% du résultat net pour le secteur boulangerie, sur la base des bilans disponibles)
FALLBACK_DEPRECIATION_RATIO = 0.4

# Ajustement prudent des éléments non récurrents (milieu de la fourchette 10-15%)
NON_RECURRENT_ADJUST_RATE = 0.12


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _compute_ebe_normalise(fy: FinancialYear, adjust_non_recurrent: float = 0.0) -> float:
    """
    EBE normatif = Résultat d'exploitation + Dotations aux amortissements
    ajusté des éléments non récurrents.
    """
    if fy.ebe != 0:
        return fy.ebe - adjust_non_recurrent
    # Reconstruction : REX + DAP
    return fy.resultat_exploitation + fy.dotations_amortissements - adjust_non_recurrent


def _compute_dette_nette(fy: FinancialYear) -> float:
    """
    Dette nette = Emprunts LT + Emprunts CT - Disponibilités
    """
    return fy.emprunts_lt + fy.emprunts_ct - fy.disponibilites


def _compute_bfr(fy: FinancialYear) -> float:
    """
    BFR = Stocks + Créances clients - Dettes fournisseurs - Dettes fiscales/sociales
    """
    return (
        fy.stocks
        + fy.creances_clients
        + fy.autres_creances
        - fy.dettes_fournisseurs
        - fy.dettes_fiscales_sociales
    )


# ---------------------------------------------------------------------------
# Méthodes de valorisation
# ---------------------------------------------------------------------------

def _valuation_multiples(ebitda: float, multiple_low: float, multiple_mid: float,
                         multiple_high: float, method_name: str,
                         notes: str = "") -> ValuationRange:
    return ValuationRange(
        low=ebitda * multiple_low,
        mid=ebitda * multiple_mid,
        high=ebitda * multiple_high,
        method=method_name,
        notes=notes,
    )


def _valuation_dcf(ebitda: float, capex_maintenance: float, bfr_variation: float,
                   taxes: float = 0.25) -> ValuationRange:
    """
    DCF simplifié sur 5 ans avec valeur terminale (Gordon-Shapiro).
    Free Cash-Flow = EBITDA * (1 - tax) - capex_maintenance - ΔBFR
    """
    nopat = ebitda * (1 - taxes)
    fcf = nopat - capex_maintenance - bfr_variation

    # Actualisation des FCF
    pv_fcf = sum(fcf / (1 + WACC) ** t for t in range(1, DCF_YEARS + 1))

    # Valeur terminale
    terminal_value = (fcf * (1 + GROWTH_TERMINAL)) / (WACC - GROWTH_TERMINAL)
    pv_terminal = terminal_value / (1 + WACC) ** DCF_YEARS

    central = pv_fcf + pv_terminal
    return ValuationRange(
        low=central * 0.80,
        mid=central,
        high=central * 1.20,
        method="DCF (5 ans, WACC 12%)",
        notes=f"FCF normatif : {fcf/1000:.0f}K€ | VT actualisée : {pv_terminal/1000:.0f}K€",
    )


def _valuation_patrimoniale(actif_net: float, goodwill_estimate: float) -> ValuationRange:
    """
    Valorisation patrimoniale = Actif Net Corrigé + survaleur estimée.
    """
    anc = actif_net
    central = anc + goodwill_estimate
    return ValuationRange(
        low=anc,
        mid=central,
        high=central * 1.1,
        method="Patrimoniale (ANC + goodwill)",
        notes=f"ANC : {anc/1000:.0f}K€ | Goodwill estimé : {goodwill_estimate/1000:.0f}K€",
    )


# ---------------------------------------------------------------------------
# Analyse principale
# ---------------------------------------------------------------------------

def _build_pros_cons_archange3(fy: FinancialYear) -> tuple[list[str], list[str]]:
    pros = [
        "Marque ANGE reconnue — 2ème réseau boulangerie France, +250 franchises.",
        "Modèle artisano-industriel unique : pain pétri sur place, titre 'boulangerie' conservé.",
        "CA en hausse de +21% entre 2021 et 2023 sur le site de Cesson-Sévigné.",
        "Résultats nets positifs sur les 2 derniers exercices connus (69K€ en 2024, 106K€ en 2023).",
        "Fort potentiel de développement : ouverture dimanche matin, livraison entreprises, brunch.",
        "Clientèle de passage et fidélisée (carte de fidélité, promotions régulières).",
        "Bail commercial 3-6-9 sécurisé, propriétaire du foncier = stabilité locative.",
        "Apprentis intégrés (8/16 salariés) → masse salariale optimisée.",
        "Secteur alimentaire résilient : demande incompressible de boulangerie-pâtisserie.",
    ]
    cons = [
        "Baisse du CA en 2024 (-3,7%) et du résultat net (-35%) vs 2023 : tendance à surveiller.",
        "Dépendance totale à la franchise ANGE (contrat de franchise, redevances, droit d'entrée 15K€).",
        "Concentration géographique sur un seul site = risque opérationnel maximal.",
        "Personnel clé : dirigeant vendeur, risque de départ des boulangers formés.",
        "Secteur sous pression concurrentielle : GMS, autres franchises, artisans indépendants.",
        "Capex de rénovation à prévoir à Cesson (120-150K€ partie lunch) non encore réalisé.",
        "Faibles capitaux propres (75K€) au regard du total bilan (348K€) : levier financier élevé.",
        "Dette résiduelle PGE encore en cours de remboursement.",
    ]
    return pros, cons


def _build_pros_cons_lavange(fy: FinancialYear) -> tuple[list[str], list[str]]:
    pros = [
        "Croissance du CA de +9,3% entre 2022 et 2023 (872K€ → 953K€).",
        "Résultat net 2023 en forte hausse : +108% (40K€ → 83K€).",
        "Résultat d'exploitation 2023 : 89K€ (+135% vs 2022), démontrant un effet ciseau positif.",
        "Rénovation partie lunch réalisée en 2024 (120K€) : site modernisé et valorisé.",
        "Flux de clientèle élevé : ~500 clients/jour, panier moyen 7€.",
        "Axes de développement identifiés : stand aux Halles de Laval, nouvelle boutique.",
        "Marque ANGE — meilleure franchise alimentaire France 2023.",
        "Capitaux propres reconstitués : 94K€ en 2023 vs 53K€ en 2022.",
    ]
    cons = [
        "Dettes financières importantes en 2022 (emprunts 157K€ + divers 112K€), en cours de réduction.",
        "Dépendance à la franchise ANGE (droit d'entrée 50K€ à l'actif).",
        "Site unique à Laval : risque de concentration opérationnelle.",
        "Résultats 2021 positifs (59K€) puis baisse 2022 (40K€) : volatilité historique.",
        "Subventions d'exploitation (34K€ en 2023) partiellement non récurrentes.",
        "Zone Mayenne-Laval : bassin d'emploi limité, recrutement de boulangers qualifiés difficile.",
        "Bail commercial dépendant du propriétaire SCI (lié au vendeur) : risque de renouvellement.",
    ]
    return pros, cons


def _questions_vendeur() -> list[str]:
    return [
        "Qualité des comptes : méthodes comptables spécifiques ? Changements de règles comptables récents ?",
        "Récurrence des ajustements exceptionnels sur les 3 derniers exercices.",
        "BFR : saisonnalité forte (fêtes, été) ? Délais clients/fournisseurs réels ? Litiges et créances douteuses ?",
        "Trésorerie & dette : détail des lignes de crédit, covenants PGE, engagements hors-bilan, garanties.",
        "EBE normatif : quels éléments non récurrents ont gonflé ou réduit les résultats sur 3 ans ?",
        "Rémunération des dirigeants : quel niveau est inclus dans les charges ? Avantages en nature ?",
        "Capex maintenance vs croissance : quel backlog d'investissements non encore réalisés ?",
        "Clients & revenus : concentration ? Clauses de résiliation de contrats de livraison ? Remises accordées ?",
        "Contrat de franchise ANGE : durée restante, conditions de renouvellement, clauses de résiliation, redevances ?",
        "Stocks & provisions : méthode de valorisation des stocks ? Provisions pour dépréciation ?",
        "Fiscalité : contrôles en cours, passifs latents, déficits reportables éventuels ?",
        "Immobilier : bail Cesson détenu par SCI du vendeur — conditions de cession/transfert du bail ?",
        "Social : contentieux prud'homaux en cours ? Accords d'intéressement ? Turn-over des équipes ?",
    ]


def _leviers_negociation(company_name: str, ebitda: float) -> list[str]:
    return [
        f"Normalisation prudente des résultats : retirer subventions non récurrentes et produits exceptionnels "
        f"(impact estimé -10 à -15% sur EBE normatif, soit -{ebitda * NON_RECURRENT_ADJUST_RATE / 1000:.0f}K€).",
        "Décote de concentration opérationnelle : site unique, dépendance au dirigeant → -0,5x multiple EBE.",
        "Décote franchise : redevances, contraintes ANGE, risque non-renouvellement contrat → -0,5x multiple.",
        "Ajustement BFR : intégrer la saisonnalité et les besoins en fonds de roulement de lancement.",
        "Capex de maintien réaliste : rénovation prévue (120-150K€) à intégrer en dette nette équivalente.",
        "Passifs hors-bilan : garanties de passif à demander pour couvrir litiges sociaux/fiscaux latents.",
        "Earn-out : part variable du prix conditionnée à la performance 2025 (objectif CA ≥ N-1).",
        "Séquestre de 10-15% du prix pendant 18-24 mois pour couvrir les risques identifiés.",
        "Conditions de transfert du bail Cesson (SCI du vendeur) : risque à déduire du prix ou garantie spécifique.",
    ]


def analyze_company(company: CompanyData) -> CompanyAnalysis:
    """
    Réalise l'analyse financière complète d'une entreprise.
    """
    analysis = CompanyAnalysis(company=company)

    # Exercice le plus récent avec données complètes (EBE ou résultat net disponible)
    fy = next(
        (y for y in company.sorted_years
         if y.chiffre_affaires > 0 and (y.ebe > 0 or y.resultat_net > 0)),
        None,
    )
    if fy is None:
        return analysis

    # EBE normatif (ajusté subventions non récurrentes ~20%)
    subv_recurrentes_ratio = 0.80
    ebe_raw = _compute_ebe_normalise(fy)
    # Heuristique : si EBE < résultat net, reconstruire via ratio de dépréciation
    if ebe_raw < fy.resultat_net and fy.resultat_net > 0:
        ebe_raw = fy.resultat_net + max(
            fy.dotations_amortissements, fy.resultat_net * FALLBACK_DEPRECIATION_RATIO
        )

    # Ajustement pour subventions non récurrentes (ex-France Relance)
    subv_adjust = getattr(fy, "subventions_exploitation", 0) * (1 - subv_recurrentes_ratio)
    analysis.ebitda_normalise = max(ebe_raw - subv_adjust, 0)
    analysis.ebit_normalise = analysis.ebitda_normalise - max(
        fy.dotations_amortissements, analysis.ebitda_normalise * 0.15
    )

    # Dette nette
    analysis.dette_nette = _compute_dette_nette(fy)
    analysis.tresorerie_nette = fy.disponibilites - fy.emprunts_ct - fy.emprunts_lt
    analysis.bfr = _compute_bfr(fy)

    # Ratios
    analysis.ratio_marge_nette = _safe_div(fy.resultat_net, fy.chiffre_affaires) * 100
    analysis.ratio_marge_ebe = _safe_div(analysis.ebitda_normalise, fy.chiffre_affaires) * 100
    analysis.ratio_endettement = _safe_div(analysis.dette_nette, analysis.ebitda_normalise)
    analysis.rotation_bfr_jours = _safe_div(analysis.bfr, fy.chiffre_affaires) * 365

    ebitda = analysis.ebitda_normalise
    capex_maint = ebitda * 0.08  # ~8% de l'EBITDA pour la maintenance des équipements boulangerie

    # ----- Valorisations -----
    v_multiples_ebe = _valuation_multiples(
        ebitda, MULTIPLE_EBE_LOW, MULTIPLE_EBE_MID, MULTIPLE_EBE_HIGH,
        "Multiples EBE (3x–5,5x)",
        notes=(
            "Multiples sectoriels boulangerie franchise France 2024 : "
            "3x (risque élevé / mono-site) à 5,5x (croissance forte / marque reconnue)."
        ),
    )

    v_dcf = _valuation_dcf(
        ebitda=ebitda,
        capex_maintenance=capex_maint,
        bfr_variation=max(analysis.bfr * 0.05, 0),
        taxes=0.25,
    )

    actif_net = fy.capitaux_propres
    goodwill = ebitda * 1.5  # survaleur = 1,5x EBE (clientèle + enseigne)
    v_patrim = _valuation_patrimoniale(actif_net, goodwill)

    analysis.valuations = [v_multiples_ebe, v_dcf, v_patrim]

    # Fourchette resserrée : pondération multiples 50%, DCF 30%, patrimoniale 20%
    ve_low = (
        v_multiples_ebe.low * 0.50
        + v_dcf.low * 0.30
        + v_patrim.low * 0.20
    )
    ve_high = (
        v_multiples_ebe.high * 0.50
        + v_dcf.high * 0.30
        + v_patrim.high * 0.20
    )
    analysis.valeur_entreprise_retenue = (ve_low + ve_high) / 2

    # Valeur des titres = VE - dette nette
    analysis.valeur_titres = analysis.valeur_entreprise_retenue - max(analysis.dette_nette, 0)

    # Pros / Cons
    if "ARCH'ANGE3" in company.name:
        analysis.pros, analysis.cons = _build_pros_cons_archange3(fy)
    else:
        analysis.pros, analysis.cons = _build_pros_cons_lavange(fy)

    analysis.questions_vendeur = _questions_vendeur()
    analysis.leviers_negociation = _leviers_negociation(company.name, ebitda)

    return analysis


def analyze_consolidated(a3: CompanyData, lavange: CompanyData) -> dict:
    """
    Analyse consolidée des deux entités (vision portefeuille acquéreur).
    """
    ana3 = analyze_company(a3)
    ana_l = analyze_company(lavange)

    fy3 = a3.sorted_years[0] if a3.sorted_years else None
    fyl = next((y for y in lavange.sorted_years if y.chiffre_affaires > 0 and y.year != "2024"), None)

    ca_total = (fy3.chiffre_affaires if fy3 else 0) + (fyl.chiffre_affaires if fyl else 0)
    ebitda_total = ana3.ebitda_normalise + ana_l.ebitda_normalise
    dette_nette_total = ana3.dette_nette + ana_l.dette_nette

    ve_total_low = sum(v.low for v in ana3.valuations[:1]) + sum(v.low for v in ana_l.valuations[:1])
    ve_total_high = sum(v.high for v in ana3.valuations[:1]) + sum(v.high for v in ana_l.valuations[:1])

    return {
        "archange3": ana3,
        "lavange": ana_l,
        "consolide": {
            "ca_total": ca_total,
            "ebitda_total": ebitda_total,
            "dette_nette_total": dette_nette_total,
            "ve_fourchette": (ve_total_low, ve_total_high),
            "valeur_titres_totale": (
                ve_total_low - max(dette_nette_total, 0),
                ve_total_high - max(dette_nette_total, 0),
            ),
        },
    }
