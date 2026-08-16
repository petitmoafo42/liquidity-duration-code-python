"""
================================================================================
CALCUL DE LA DURATION DE LIQUIDITE -- Memoire de Master, Steve MOAFO
Partie III : Application empirique et stress tests a l'horizon 2027
================================================================================

Ce script implemente numeriquement le cadre theorique de la Partie II
(courbe de liquidite, duration de liquidite) applique au portefeuille
synthetique construit en III.1.2.

PRINCIPE DE TRANSPARENCE METHODOLOGIQUE
----------------------------------------
Chaque parametre utilise est etiquete SOURCE ou HYPOTHESE :

  - SOURCE    : donnee publique verifiable, avec reference precise
                (ACPR, EIOPA, Banque de France, litterature academique).
  - HYPOTHESE : parametre de calibration choisi par l'auteur du memoire,
                car aucune donnee publique ne documente ce parametre a
                l'echelle de granularite requise (ex. spread moyen par
                classe d'actif, volume quotidien echangeable, coefficients
                d'impact de marche). Ces valeurs sont des ordres de
                grandeur informes par la litterature de microstructure
                (Bangia et al., 1999 ; conventions usuelles des modeles
                d'impact de marche de type Almgren-Chriss), MAIS ne sont
                PAS des donnees observees pour le marche francais.

Les resultats numeriques de ce script doivent donc etre lus comme une
ILLUSTRATION QUANTIFIEE du cadre conceptuel propose, calibree sur les
meilleurs ordres de grandeur disponibles, et non comme une estimation
econometrique du risque de liquidite reel des assureurs francais.
================================================================================
"""

import numpy as np
import pandas as pd
import json

# ==============================================================================
# BLOC 1 -- PORTEFEUILLE SYNTHETIQUE  [SOURCE : ACPR, Analyses et syntheses
#            n°173, fin decembre 2024 -- voir memoire, tableau III.1.2]
# ==============================================================================

PORTEFEUILLE = pd.DataFrame([
    # classe                                 poids   source
    ("Obligations souveraines zone euro",     0.19,  "ACPR (2025b), source"),
    ("Obligations d'entreprises",             0.37,  "ACPR (2025b), source"),
    ("Actions et participations",             0.22,  "ACPR (2025b), source"),
    ("OPC non ventiles",                      0.16,  "ACPR (2025b), source"),
    ("Immobilier",                            0.04,  "Hypothese calibree"),
    ("Tresorerie et depots",                  0.02,  "Hypothese calibree"),
], columns=["classe", "poids", "origine"])

assert abs(PORTEFEUILLE["poids"].sum() - 1.0) < 1e-9, "Le portefeuille doit sommer a 100%"

TOTAL_PLACEMENTS_MDS_EUR = 2672.0   # SOURCE : ACPR n°173, fin decembre 2024

# ==============================================================================
# BLOC 2 -- CALIBRATION MICROSTRUCTURE PAR CLASSE D'ACTIF  [HYPOTHESE]
# ==============================================================================
#
# Modele de cout de cession (deja pose en III.2.2 du memoire) :
#
#     C_i(h) = c_i^spread + lambda_i * ( Q_i / (h * pi * V_i) )^gamma_i
#
# ou :
#   c_i^spread : demi-spread acheteur-vendeur de la classe i (cout incompressible)
#   Q_i        : quantite a ceder dans la classe i (en % de l'encours de la classe)
#   h          : horizon de cession accorde (jours ouvres)
#   pi         : taux de participation maximal au volume quotidien (convention
#                usuelle des modeles d'execution : 10-15%, cf. Almgren-Chriss)
#   V_i        : volume quotidien echangeable de la classe i, exprime en % de
#                l'encours total de cette classe (proxy de "turnover" journalier)
#   lambda_i   : parametre d'echelle du cout d'impact (en % de la valeur cedee)
#   gamma_i    : elasticite du cout d'impact (loi de puissance ; gamma=0.5
#                correspond a la "square-root law" standard en microstructure)
#
# Interpretation : Q_i/(pi*V_i) est le nombre de jours necessaires pour ceder
# la position au taux de participation maximal ; rapporte a l'horizon h, ce
# ratio mesure le degre d'urgence de la cession. Si h est tres superieur a ce
# delai technique, le ratio tend vers 0 et C_i(h) -> c_i^spread (cout plancher).
# Si h est tres inferieur, le cout explose (cession forcee, hors marche).

CALIBRATION = pd.DataFrame([
    # classe                          c_spread(bp)  V_i(%/jour)  gamma   lambda(%)
    ("Obligations souveraines zone euro",   3,        0.60,       0.50,    1.2),
    ("Obligations d'entreprises",          18,        0.20,       0.55,    2.5),
    ("Actions et participations",           6,        0.90,       0.50,    1.0),
    ("OPC non ventiles",                   25,        0.15,       0.60,    3.5),
    ("Immobilier",                        150,        0.02,       0.85,   12.0),
    ("Tresorerie et depots",                1,       50.00,       0.30,    0.05),
], columns=["classe", "c_spread_bp", "V_pct_jour", "gamma", "lambda_pct"])

PI_PARTICIPATION = 0.12   # HYPOTHESE : taux de participation maximal au marche (12%)

# Sources qualitatives justifiant les ORDRES DE GRANDEUR retenus (pas les
# valeurs elles-memes, qui restent des hypotheses) :
#   - Spreads souverains zone euro (qq points de base) et corporate IG
#     (10-30 pb) : ordres de grandeur usuels de la litterature de
#     microstructure obligataire (cf. Bangia et al., 1999).
#   - Immobilier : cout de cession tres eleve a court terme, coherent avec
#     le classement en horizon ">60 jours" retenu au tableau III.1.3 du
#     memoire (illiquidite quasi totale aux horizons courts).
#   - gamma proche de 0.5 : convention standard des modeles d'impact de
#     marche de type "square-root law" (Almgren, Thum, Hauptmann, Li, 2005).

print("Portefeuille synthetique charge :", len(PORTEFEUILLE), "classes")
print("Calibration microstructure chargee :", len(CALIBRATION), "classes")

PORTEFEUILLE.to_csv("portefeuille.csv", index=False)
CALIBRATION.to_csv("calibration.csv", index=False)

# ==============================================================================
# BLOC 3 -- SCENARIOS DE STRESS  [SOURCE pour le choc de taux et de spread :
#            deja definis par le memoire, Annexe B, tableau III.2.1 /
#            "mass lapse" SCR Solvabilite II = 40% -- SOURCE reglementaire]
# ==============================================================================

# Choc de taux et de spread : deja fixes dans le memoire (Annexe B)
SCENARIOS = pd.DataFrame([
    # nom            choc_taux_pb   choc_spread_pb   mult_rachat   profondeur_marche
    ("Central",              0,             0,           1.0,           1.00),
    ("Choc de taux",       200,             0,           1.5,           0.85),
    ("Crise de spread",      0,           150,           1.3,           0.70),
    ("Choc combine",       200,           150,           2.0,           0.55),
], columns=["scenario", "choc_taux_pb", "choc_spread_pb", "mult_rachat", "prof_marche"])
# profondeur_marche : facteur multiplicatif applique a V_i sous stress
# (HYPOTHESE : la profondeur de marche se contracte en cas de choc, cf.
# discussion qualitative en I.1.2 "la liquidite de marche" du memoire).

# --- Ancrage du besoin de liquidite : taux de rachat de base -------------
# SOURCE : ACPR (2025b), ratio rachats / provisions mathematiques = 4,7% en
# 2024 pour l'ensemble du marche francais (cf. I.3.3 du memoire).
TAUX_RACHAT_BASE = 0.047

# SOURCE reglementaire : le choc de rachat massif ("mass lapse") du SCR
# standard Solvabilite II est fixe a 40% de l'encours (Directive 2009/138/CE,
# reglement delegue (UE) 2015/35, art. 142). Il sert ICI de borne superieure
# de plausibilite pour verifier que les scenarios de stress retenus restent
# dans un ordre de grandeur regulierement inferieur au choc extreme du
# pilier 1, et non comme un scenario directement simule.
MASS_LAPSE_SCR = 0.40

# --- Part des sorties absorbee par les flux ordinaires (primes, coupons) --
# HYPOTHESE : en toutes circonstances, une fraction des rachats est
# compensee par les entrees courantes (primes encaissees, coupons et
# remboursements a echeance), evitant une cession d'actifs a due
# concurrence. Cette fraction est calibree a 50% en scenario central et
# reduite sous stress (les entrees ralentissent alors que les sorties
# augmentent), conformement a la logique du besoin net de liquidite Q_t
# formalisee en Partie II (eq. 2.2.2) du memoire.
TAUX_ABSORPTION = {"Central": 0.50, "Choc de taux": 0.35,
                    "Crise de spread": 0.40, "Choc combine": 0.20,
                    # Scenarios de decomposition (bloc 9) : meme logique que
                    # "Choc de taux", ventilee selon le canal isole --
                    # Sim1 (marche seul, rachats inchanges) -> absorption
                    # identique au central (les rachats n'augmentent pas) ;
                    # Sim2 (rachats seuls) -> absorption identique a "Choc
                    # de taux" (meme choc de rachat que le scenario complet).
                    "Sim1 - Effet direct (marche seul, hausse)": 0.50,
                    "Sim2 - Effet volume seul (rachats, hausse)": 0.35}

print("\nScenarios de stress (deja definis au memoire, Annexe B) :")
print(SCENARIOS.to_string(index=False))
print(f"\nTaux de rachat de base (SOURCE ACPR 2024) : {TAUX_RACHAT_BASE:.1%}")
print(f"Choc de rachat massif SCR Solvabilite II (SOURCE reglementaire, "
      f"reference de plausibilite) : {MASS_LAPSE_SCR:.0%}")

# ==============================================================================
# BLOC 4 -- FONCTION DE COUT DE CESSION (eq. III.2.2 du memoire)
# ==============================================================================

def cout_cession(c_spread_bp, V_pct_jour, gamma, lambda_pct, Q_rel, h, pi=PI_PARTICIPATION):
    """
    Cout relatif de cession C_i(h) pour la classe i.

    Parametres
    ----------
    c_spread_bp : demi-spread acheteur-vendeur (points de base)
    V_pct_jour  : volume quotidien echangeable, en % de l'encours DE LA CLASSE
    gamma       : elasticite de la loi d'impact
    lambda_pct  : parametre d'echelle de l'impact (%)
    Q_rel       : quantite a ceder, en fraction de l'encours DE LA CLASSE (0 a 1+)
    h           : horizon de cession, en jours ouvres
    pi          : taux de participation maximal au marche

    Retour : cout relatif (fraction, ex. 0.02 = 2%)
    """
    c_spread = c_spread_bp / 10_000.0
    if Q_rel <= 1e-12:
        return c_spread
    jours_necessaires = Q_rel / (pi * V_pct_jour / 100.0)
    ratio_urgence = jours_necessaires / h
    impact = (lambda_pct / 100.0) * (ratio_urgence ** gamma)
    return c_spread + impact


# ==============================================================================
# BLOC 5 -- ORDRE DE LIQUIDATION ("PECKING ORDER")  [reprend la logique
#            qualitative deja exposee en I.1.2 du memoire : l'assureur cede
#            d'abord sa tresorerie et les actifs les plus liquides]
# ==============================================================================

ORDRE_LIQUIDATION = [
    "Tresorerie et depots",
    "Obligations souveraines zone euro",
    "Actions et participations",
    "Obligations d'entreprises",
    "OPC non ventiles",
    "Immobilier",
]

def allouer_besoin_liquidite(besoin_total_pct_portefeuille, poids):
    """
    Repartit un besoin net de liquidite (en % du portefeuille TOTAL) entre
    les classes d'actifs, en suivant l'ordre de liquidation ci-dessus,
    jusqu'a epuisement du besoin ou de l'encours disponible dans chaque
    classe (plafond = encours total de la classe).

    Retourne un dict {classe: montant preleve, en % du portefeuille total}.
    """
    reste = besoin_total_pct_portefeuille
    alloc = {c: 0.0 for c in poids.index}
    for classe in ORDRE_LIQUIDATION:
        if reste <= 1e-12:
            break
        disponible = poids[classe]
        prelevement = min(reste, disponible)
        alloc[classe] = prelevement
        reste -= prelevement
    return alloc, reste  # reste > 0 signale un besoin non couvert (severe)


# ==============================================================================
# BLOC 6 -- EFFET DU CHOC DE SPREAD SUR LE DEMI-SPREAD PAR CLASSE [HYPOTHESE]
# ==============================================================================
# Transmission partielle du choc de spread de credit (Annexe B) selon la
# sensibilite credit de chaque classe : plein effet sur le corporate, effet
# nul sur le souverain zone euro (fuite vers la qualite), effet partiel sur
# les OPC (exposition mixte), effet nul sur actions/immobilier/tresorerie
# (chocs de nature differente, deja capture par la contraction de V_i).
SENSIBILITE_SPREAD = {
    "Obligations souveraines zone euro": 0.0,
    "Obligations d'entreprises":         1.0,
    "Actions et participations":         0.0,
    "OPC non ventiles":                  0.5,
    "Immobilier":                        0.0,
    "Tresorerie et depots":              0.0,
}

print("\nModele de cout de cession et ordre de liquidation charges.")

# ==============================================================================
# BLOC 7 -- CALCUL DU BESOIN NET DE LIQUIDITE PAR SCENARIO
# ==============================================================================

def besoin_net_liquidite(scenario_row):
    """Besoin net de liquidite, en % du portefeuille total (eq. 2.2.2 du memoire)."""
    nom = scenario_row["scenario"]
    rachat_brut = TAUX_RACHAT_BASE * scenario_row["mult_rachat"]
    absorption = TAUX_ABSORPTION[nom]
    return rachat_brut * (1 - absorption)

BESOINS = SCENARIOS.copy()
BESOINS["besoin_net_pct"] = BESOINS.apply(besoin_net_liquidite, axis=1)
print("\nBesoin net de liquidite par scenario (% du portefeuille total) :")
print(BESOINS[["scenario", "besoin_net_pct"]].to_string(index=False,
      formatters={"besoin_net_pct": "{:.3%}".format}))

# ==============================================================================
# BLOC 8 -- COUT DE CESSION DU PORTEFEUILLE C_P(h) PAR SCENARIO
#            (eq. 31 du memoire : C_P(h,r) = somme_i  w_i * C_i(h,r,q_i))
# ==============================================================================

HORIZONS = np.array([1, 2, 3, 5, 8, 10, 15, 20, 30, 45, 60, 90, 120])  # jours ouvres

poids_idx = PORTEFEUILLE.set_index("classe")["poids"]
calib_idx = CALIBRATION.set_index("classe")

def cout_portefeuille(scenario_row, h):
    """
    Calcule C_P(h) pour un scenario et un horizon donnes, ainsi que le
    detail par classe (utile pour les graphiques et la decomposition).
    """
    besoin = besoin_net_liquidite(scenario_row)
    alloc, reste_non_couvert = allouer_besoin_liquidite(besoin, poids_idx)

    cout_total = 0.0
    detail = {}
    for classe in poids_idx.index:
        w_i = poids_idx[classe]
        q_i_total_pct = alloc[classe]                  # en % du portefeuille total
        q_i_rel = q_i_total_pct / w_i if w_i > 0 else 0.0   # en % de l'encours de la classe

        row = calib_idx.loc[classe]
        c_spread_bp = row["c_spread_bp"] + (
            scenario_row["choc_spread_pb"] * SENSIBILITE_SPREAD[classe]
        )
        V_i = row["V_pct_jour"] * scenario_row["prof_marche"]   # profondeur reduite sous stress
        V_i = max(V_i, 1e-6)

        c_i = cout_cession(c_spread_bp, V_i, row["gamma"], row["lambda_pct"], q_i_rel, h)
        detail[classe] = {"q_i_rel": q_i_rel, "c_i": c_i, "w_i": w_i}
        cout_total += w_i * c_i

    return cout_total, detail, reste_non_couvert


# --- Construction de la surface complete horizon x scenario -----------------
lignes = []
for _, scen in SCENARIOS.iterrows():
    for h in HORIZONS:
        c_p, detail, reste = cout_portefeuille(scen, h)
        lignes.append({
            "scenario": scen["scenario"], "horizon_j": h,
            "cout_portefeuille": c_p, "besoin_non_couvert": reste,
        })
SURFACE = pd.DataFrame(lignes)
SURFACE.to_csv("surface_horizon_scenario.csv", index=False)

print("\nSurface horizon x scenario calculee :", len(SURFACE), "points")
print("\nExtrait (horizon = 10 jours) :")
print(SURFACE[SURFACE["horizon_j"] == 10][["scenario", "cout_portefeuille"]]
      .to_string(index=False, formatters={"cout_portefeuille": "{:.4%}".format}))

# ==============================================================================
# BLOC 9 -- SCENARIOS DE DECOMPOSITION (methode a trois simulations,
#            deja annoncee en Partie II, section 2.1.3, du memoire)
# ==============================================================================
# Le scenario "Choc de taux" combine DEUX canaux : (i) une contraction de la
# profondeur de marche (prof_marche = 0.85) et (ii) une hausse des rachats
# (mult_rachat = 1.5). On isole chaque canal separement :

SCENARIOS_DECOMP = pd.DataFrame([
    ("Sim1 - Effet direct (marche seul, hausse)",     200, 0, 1.0, 0.85),
    ("Sim2 - Effet volume seul (rachats, hausse)",     200, 0, 1.5, 1.00),
], columns=["scenario", "choc_taux_pb", "choc_spread_pb", "mult_rachat", "prof_marche"])

# ==============================================================================
# BLOC 9 BIS -- SCENARIO SYMETRIQUE DE BAISSE DES TAUX  [HYPOTHESE]
# ==============================================================================
# Le memoire (Partie II, eq. 23 et 32) definit la duration de liquidite par une
# DIFFERENCE FINIE CENTREE, requerant un choc de taux a la hausse ET a la
# baisse. Les scenarios de stress de la section III.2.1 (tableau Annexe B) ne
# documentent qu'un choc a la hausse (+200 pb), car seule cette direction est
# pertinente pour un stress test de liquidite au sens strict (une baisse des
# taux n'est pas un scenario de tension). Pour calculer la duration selon la
# definition exacte de la Partie II, un scenario symetrique de baisse des taux
# est construit ICI, par MIROIR LINEAIRE du scenario "Choc de taux" autour du
# scenario central -- hypothese coherente avec la specification linéaire du
# modele de rachat (eq. rachats-modele, Partie II) : si un choc de +200 pb
# multiplie les rachats par 1,5 (soit +50%), un choc symetrique de -200 pb les
# multiplie par 0,5 (soit -50%) ; de meme, la profondeur de marche, degradee de
# 15% sous choc haussier (facteur 0,85), est symetriquement amelioree de 15%
# sous le choc baissier (facteur 1,15). Ce scenario n'est utilise QUE pour le
# calcul de la difference finie centree ; il n'est pas un scenario de stress
# et n'apparait pas dans le tableau des scenarios retenus (III.2.1).

SCENARIOS_BAISSE = pd.DataFrame([
    ("Choc de taux (baisse symétrique)",              -200, 0, 0.5, 1.15),
    ("Sim1 - Effet direct (marche seul, baisse)",      -200, 0, 1.0, 1.15),
    ("Sim2 - Effet volume seul (rachats, baisse)",     -200, 0, 0.5, 1.00),
], columns=["scenario", "choc_taux_pb", "choc_spread_pb", "mult_rachat", "prof_marche"])

for nom in SCENARIOS_BAISSE["scenario"]:
    TAUX_ABSORPTION[nom] = 0.50  # meme convention d'absorption que le scenario central

DELTA_R = 0.02  # 200 points de base, en decimal -- SOURCE : deja fixe au memoire (Annexe B)

def _trouver_scenario(nom):
    for table in (SCENARIOS, SCENARIOS_DECOMP, SCENARIOS_BAISSE):
        if nom in table["scenario"].values:
            return table[table["scenario"] == nom].iloc[0]
    raise KeyError(nom)

def duration_liquidite_centree(nom_scenario_hausse, nom_scenario_baisse, horizons=HORIZONS):
    """
    Duration de liquidite par DIFFERENCE FINIE CENTREE, conforme a la
    definition exacte de la Partie II (eq. 23) :

        D_L^r(h) = [C_P(h, r+Δr) - C_P(h, r-Δr)] / (2 Δr) / C_P(h, r)
    """
    scen_central = SCENARIOS[SCENARIOS["scenario"] == "Central"].iloc[0]
    scen_up = _trouver_scenario(nom_scenario_hausse)
    scen_down = _trouver_scenario(nom_scenario_baisse)

    resultats = []
    for h in horizons:
        c_central, _, _ = cout_portefeuille(scen_central, h)
        c_up, _, _ = cout_portefeuille(scen_up, h)
        c_down, _, _ = cout_portefeuille(scen_down, h)
        d_l = (c_up - c_down) / (2 * DELTA_R) / c_central
        resultats.append({"horizon_j": h, "C_central": c_central,
                           "C_up": c_up, "C_down": c_down, "D_L": d_l})
    return pd.DataFrame(resultats)

DURATION_TOTALE = duration_liquidite_centree(
    "Choc de taux", "Choc de taux (baisse symétrique)")
DURATION_DIRECTE = duration_liquidite_centree(
    "Sim1 - Effet direct (marche seul, hausse)", "Sim1 - Effet direct (marche seul, baisse)")
DURATION_VOLUME = duration_liquidite_centree(
    "Sim2 - Effet volume seul (rachats, hausse)", "Sim2 - Effet volume seul (rachats, baisse)")

DURATION_TOTALE.to_csv("duration_totale.csv", index=False)
DURATION_DIRECTE.to_csv("duration_directe.csv", index=False)
DURATION_VOLUME.to_csv("duration_volume.csv", index=False)

print("\nDuration de liquidite totale D_L^r(h) -- difference finie CENTREE",
      "(+200pb / -200pb autour du scenario central) :")
print(DURATION_TOTALE[["horizon_j", "D_L"]].to_string(index=False,
      formatters={"D_L": "{:.2f}".format}))
print("\nPart de l'effet volume (rachats) dans la duration totale, par horizon :")
part_volume = (DURATION_VOLUME["D_L"] / DURATION_TOTALE["D_L"] * 100)
for h, p in zip(HORIZONS, part_volume):
    print(f"  h={h:3d}j : {p:5.1f}%")


# ==============================================================================
# BLOC 10 -- FIGURES
# ==============================================================================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

plt.rcParams.update({
    "font.family": "serif", "font.size": 10.5,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "-",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 150,
})

COULEURS_SCEN = {
    "Central": "#2c3e50", "Choc de taux": "#c0392b",
    "Crise de spread": "#d68910", "Choc combine": "#7d3c98",
}

# --- Figure 1 : courbes de cout de cession par classe d'actif ---------------
h_fin = np.linspace(1, 120, 200)
# Quantite de reference STANDARDISEE (5% de l'encours de CHAQUE classe), et
# non la ventilation effective du besoin de liquidite (bloc "waterfall") :
# l'objectif ici est de comparer le PROFIL de liquidite propre a chaque
# classe (illustration du modele), independamment du scenario de stress
# retenu pour le portefeuille (traite separement en figures 2 a 4).
Q_REF_ILLUSTRATION = 0.02  # HYPOTHESE : 2% de l'encours de la classe (reference plus realiste)

fig, ax = plt.subplots(figsize=(6.4, 4.2))
for classe in poids_idx.index:
    row = calib_idx.loc[classe]
    couts = [cout_cession(row["c_spread_bp"], row["V_pct_jour"], row["gamma"],
                           row["lambda_pct"], Q_REF_ILLUSTRATION, h) for h in h_fin]
    ax.plot(h_fin, np.array(couts) * 100, label=classe, linewidth=1.6)
ax.set_xlabel("Horizon de cession $h$ (jours ouvrés)")
ax.set_ylabel("Coût relatif de cession $C_i(h)$ (\\%, échelle log)")
ax.set_yscale("log")
ax.set_title("Courbes de coût de cession par classe d'actif\n"
              f"(cession de référence : {Q_REF_ILLUSTRATION:.0%} de l'encours de la classe)",
              fontsize=10)
ax.legend(fontsize=7.5, loc="upper right", framealpha=0.9)
ax.set_xlim(0, 120)
fig.tight_layout()
fig.savefig("fig_cout_par_classe.png", dpi=200)
plt.close(fig)

# --- Figure 2 : cout de cession du portefeuille par scenario -----------------
fig, ax = plt.subplots(figsize=(6.4, 4.2))
for nom_scen in SCENARIOS["scenario"]:
    sub = SURFACE[SURFACE["scenario"] == nom_scen].sort_values("horizon_j")
    ax.plot(sub["horizon_j"], sub["cout_portefeuille"] * 100, marker="o",
            markersize=3.5, linewidth=1.7, label=nom_scen,
            color=COULEURS_SCEN[nom_scen])
ax.set_xlabel("Horizon de cession $h$ (jours ouvrés)")
ax.set_ylabel("Coût de cession du portefeuille $C_P(h)$ (\\%)")
ax.set_title("Coût de cession du portefeuille selon l'horizon et le scénario", fontsize=10)
ax.legend(fontsize=8.5, loc="upper right", framealpha=0.9)
ax.set_xlim(0, 120)
fig.tight_layout()
fig.savefig("fig_surface_scenarios.png", dpi=200)
plt.close(fig)

# --- Figure 3 : duration de liquidite et decomposition direct/volume --------
fig, ax = plt.subplots(figsize=(6.4, 4.2))
ax.plot(DURATION_TOTALE["horizon_j"], DURATION_TOTALE["D_L"],
        color="#c0392b", linewidth=2.0, marker="o", markersize=3.5,
        label="Duration totale $D_L^r(h)$")
ax.plot(DURATION_VOLUME["horizon_j"], DURATION_VOLUME["D_L"],
        color="#2980b9", linewidth=1.5, linestyle="--",
        label="Effet volume (rachats) seul")
ax.plot(DURATION_DIRECTE["horizon_j"], DURATION_DIRECTE["D_L"],
        color="#16a085", linewidth=1.5, linestyle="--",
        label="Effet direct (marché) seul")
ax.set_xlabel("Horizon de cession $h$ (jours ouvrés)")
ax.set_ylabel("Duration de liquidité $D_L^r(h)$")
ax.set_title("Duration de liquidité du portefeuille et décomposition des canaux", fontsize=10)
ax.legend(fontsize=8.5, loc="upper right", framealpha=0.9)
ax.set_xlim(0, 120)
fig.tight_layout()
fig.savefig("fig_duration_decomposition.png", dpi=200)
plt.close(fig)

# --- Figure 4 : heatmap horizon x scenario -----------------------------------
fig, ax = plt.subplots(figsize=(6.4, 3.6))
pivot = SURFACE.pivot(index="scenario", columns="horizon_j", values="cout_portefeuille") * 100
pivot = pivot.reindex(["Central", "Choc de taux", "Crise de spread", "Choc combine"])
im = ax.imshow(pivot.values, aspect="auto", cmap="Reds",
               extent=[0, len(HORIZONS), 0, 4])
ax.set_xticks(np.arange(len(HORIZONS)) + 0.5)
ax.set_xticklabels(HORIZONS, fontsize=7.5)
ax.set_yticks(np.arange(4) + 0.5)
ax.set_yticklabels(pivot.index[::-1], fontsize=8.5)
ax.set_xlabel("Horizon de cession $h$ (jours ouvrés)")
for i in range(4):
    for j in range(len(HORIZONS)):
        val = pivot.values[3 - i, j]
        ax.text(j + 0.5, i + 0.5, f"{val:.1f}", ha="center", va="center",
                fontsize=6.5, color="white" if val > pivot.values.max() * 0.55 else "black")
cbar = fig.colorbar(im, ax=ax, shrink=0.85)
cbar.set_label("Coût de cession (\\%)", fontsize=8.5)
ax.set_title("Surface horizon--scénario--coût $C_P(h)$", fontsize=10)
fig.tight_layout()
fig.savefig("fig_heatmap_surface.png", dpi=200)
plt.close(fig)

print("\n4 figures generees : fig_cout_par_classe.png, fig_surface_scenarios.png,",
      "fig_duration_decomposition.png, fig_heatmap_surface.png")





