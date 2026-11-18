// Zonages relevés le 18/11/2026 par requête à la Géoplateforme IGN (BD TOPO forêts publiques, INPN Natura 2000)
// sur un rectangle autour de chaque commune. Le périmètre exact se vérifie sur les fiches officielles.
const inpn = (id) => `https://inpn.mnhn.fr/site/natura2000/${id}`;

export const SECTEURS = {
  labenne: {
    forets: ["Forêt communale de Labenne", "Forêt domaniale des Dunes-du-Sud (ONF)", "Terrains du Conservatoire du littoral à Capbreton, canton de la Pointe"],
    natura: [["FR7200713", "Dunes modernes du littoral landais de Capbreton à Tarnos"], ["FR7200719", "Zones humides associées au marais d'Orx"], ["FR7210063", "Domaine d'Orx (zone de protection spéciale)"]],
  },
  capbreton: {
    forets: ["Forêt communale de Capbreton", "Forêt domaniale des Dunes-du-Sud (ONF)", "Terrains du Conservatoire du littoral, canton de la Pointe"],
    natura: [["FR7200713", "Dunes modernes du littoral landais de Capbreton à Tarnos"]],
  },
  hossegor: {
    forets: ["Forêt communale de Soorts-Hossegor", "Forêt domaniale des Dunes-du-Sud (ONF)"],
    natura: [],
  },
  seignosse: {
    forets: ["Forêt communale de Seignosse", "Forêt domaniale des Dunes-du-Sud (ONF)", "Terrains du Conservatoire du littoral à Seignosse, canton de la Semis"],
    natura: [["FR7200712", "Dunes modernes du littoral landais de Vieux-Boucau à Hossegor"], ["FR7200717", "Zones humides de l'arrière-dune du Marensin"]],
  },
};
export { inpn };
