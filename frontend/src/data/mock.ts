import type {
  ActivityItem,
  AgentDetail,
  AnalysisResult,
  CategorySlice,
  ChatMessage,
  DocumentItem,
  MonthlyAnalysis,
  PipelineRun,
  StatCard,
  Suggestion,
  User,
} from '@/types'

export const currentUser: User = {
  id: 'u-1',
  name: 'Me. Reda El Amrani',
  role: 'Administrateur',
  email: 'reda.elamrani@legallink.ma',
  initials: 'RE',
}

export const dashboardStats: StatCard[] = [
  {
    id: 's1',
    label: 'Contrats analysés',
    value: '148',
    trend: '+12%',
    trendUp: true,
    sparkline: [12, 18, 14, 22, 20, 28, 26, 32],
  },
  {
    id: 's2',
    label: 'Analyses en cours',
    value: '7',
    trend: '+3',
    trendUp: true,
    sparkline: [2, 3, 2, 4, 5, 4, 6, 7],
  },
  {
    id: 's3',
    label: 'Temps moyen d’analyse',
    value: '6m 24s',
    trend: '-8%',
    trendUp: true,
    sparkline: [9, 8, 8, 7, 7, 6, 6, 6],
  },
  {
    id: 's4',
    label: 'Rapports générés',
    value: '96',
    trend: '+18%',
    trendUp: true,
    sparkline: [8, 10, 12, 11, 15, 18, 20, 22],
  },
]

export const recentActivity: ActivityItem[] = [
  {
    id: 'a1',
    title: 'Contrat_Fournisseur_ACM.pdf',
    subtitle: 'Analyse terminée — score 87/100',
    timeAgo: 'Il y a 8 min',
    status: 'completed',
  },
  {
    id: 'a2',
    title: 'NDA_Partenariat_2026.pdf',
    subtitle: 'Analyse en cours',
    timeAgo: 'Il y a 22 min',
    status: 'processing',
  },
  {
    id: 'a3',
    title: 'CGV_Marketplace_v3.pdf',
    subtitle: 'Risques élevés détectés',
    timeAgo: 'Il y a 1 h',
    status: 'completed',
  },
  {
    id: 'a4',
    title: 'Avenant_Bail_Commercial.pdf',
    subtitle: 'En file d’attente',
    timeAgo: 'Il y a 2 h',
    status: 'queued',
  },
  {
    id: 'a5',
    title: 'Politique_Confidentialite.pdf',
    subtitle: 'Rapport partagé avec l’équipe',
    timeAgo: 'Hier',
    status: 'completed',
  },
]

export const analysisCategories: CategorySlice[] = [
  { name: 'Commercial', value: 9, color: '#2563EB' },
  { name: 'Social', value: 5, color: '#22C55E' },
  { name: 'IT', value: 4, color: '#F59E0B' },
  { name: 'Fiscal', value: 3, color: '#8B5CF6' },
  { name: 'Compliance', value: 3, color: '#EF4444' },
]

export const monthlyAnalyses: MonthlyAnalysis[] = [
  { month: 'Jan', count: 8 },
  { month: 'Fév', count: 12 },
  { month: 'Mar', count: 10 },
  { month: 'Avr', count: 15 },
  { month: 'Mai', count: 18 },
  { month: 'Juin', count: 14 },
  { month: 'Juil', count: 21 },
]

export const documents: DocumentItem[] = [
  {
    id: 'd1',
    filename: 'Contrat_Fournisseur_ACM.pdf',
    type: 'Commercial',
    date: '17 juil. 2026 · 11:42',
    agents: ['JU', 'RI', 'CO'],
    score: 87,
    status: 'completed',
    pageCount: 24,
  },
  {
    id: 'd2',
    filename: 'NDA_Partenariat_2026.pdf',
    type: 'Compliance',
    date: '17 juil. 2026 · 10:15',
    agents: ['JU', 'CO'],
    score: 74,
    status: 'processing',
    pageCount: 8,
  },
  {
    id: 'd3',
    filename: 'CGV_Marketplace_v3.pdf',
    type: 'Commercial',
    date: '16 juil. 2026 · 18:03',
    agents: ['JU', 'FI', 'RI'],
    score: 61,
    status: 'completed',
    pageCount: 42,
  },
  {
    id: 'd4',
    filename: 'Avenant_Bail_Commercial.pdf',
    type: 'Fiscal',
    date: '16 juil. 2026 · 14:28',
    agents: ['JU'],
    score: 0,
    status: 'queued',
    pageCount: 6,
  },
  {
    id: 'd5',
    filename: 'Contrat_Travail_CDI.pdf',
    type: 'Social',
    date: '15 juil. 2026 · 09:51',
    agents: ['JU', 'SO'],
    score: 91,
    status: 'completed',
    pageCount: 12,
  },
  {
    id: 'd6',
    filename: 'MSA_Cloud_Provider.pdf',
    type: 'IT',
    date: '14 juil. 2026 · 16:20',
    agents: ['JU', 'TE', 'CO'],
    score: 78,
    status: 'completed',
    pageCount: 31,
  },
  {
    id: 'd7',
    filename: 'Politique_Confidentialite.pdf',
    type: 'Compliance',
    date: '12 juil. 2026 · 11:05',
    agents: ['CO'],
    score: 84,
    status: 'completed',
    pageCount: 9,
  },
  {
    id: 'd8',
    filename: 'Accord_Licence_Logiciel.pdf',
    type: 'IT',
    date: '10 juil. 2026 · 08:40',
    agents: ['JU', 'TE'],
    score: 69,
    status: 'failed',
    pageCount: 18,
  },
]

export const chatMessages: ChatMessage[] = [
  {
    id: 'm1',
    role: 'assistant',
    content:
      'Bonjour Me. Reda. Déposez un contrat ou posez une question juridique — je peux résumer, détecter les risques et citer les références applicables.',
    timestamp: '11:38',
  },
  {
    id: 'm2',
    role: 'user',
    content:
      'Peux-tu analyser le contrat fournisseur ACM et me signaler les clauses de responsabilité les plus sensibles ?',
    timestamp: '11:39',
  },
  {
    id: 'm3',
    role: 'assistant',
    content:
      'Bien sûr. J’ai identifié 3 points critiques liés à la limitation de responsabilité, aux pénalités de retard et à la résiliation unilatérale. Souhaitez-vous le détail page par page ?',
    timestamp: '11:40',
  },
]

export const suggestions: Suggestion[] = [
  { id: 'sg1', label: 'Résumer le contrat' },
  { id: 'sg2', label: 'Détecter les risques' },
  { id: 'sg3', label: 'Comparer avec un modèle' },
  { id: 'sg4', label: 'Extraire les obligations' },
  { id: 'sg5', label: 'Vérifier la conformité' },
]

export const analysisResult: AnalysisResult = {
  id: 'ar1',
  document: documents[0],
  score: 87,
  riskLabel: 'Risque faible',
  complianceRate: 92,
  clausesAnalyzed: 64,
  legalReferences: 18,
  agents: [
    { id: 'ag1', name: 'Analyse juridique', initials: 'JU', color: '#2563EB' },
    { id: 'ag2', name: 'Analyse des risques', initials: 'RI', color: '#F59E0B' },
    { id: 'ag3', name: 'Analyse de conformité', initials: 'CO', color: '#22C55E' },
  ],
  criticalPoints: [
    {
      id: 'cp1',
      title: 'Limitation de responsabilité trop large',
      description:
        'La clause plafonne les dommages à 50 % du montant annuel, y compris en cas de faute lourde — niveau de protection insuffisant pour le client.',
      risk: 'high',
      reference: 'Art. 1231-3 Code civil',
      page: 12,
    },
    {
      id: 'cp2',
      title: 'Pénalités de retard asymétriques',
      description:
        'Les pénalités s’appliquent uniquement au fournisseur. Aucune contrepartie n’est prévue en cas de retard de paiement du client.',
      risk: 'medium',
      reference: 'Art. 1231-5 Code civil',
      page: 8,
    },
    {
      id: 'cp3',
      title: 'Résiliation unilatérale sans préavis suffisant',
      description:
        'Préavis de 15 jours seulement pour une prestation critique. Recommandation : porter à 60 jours ouvrés.',
      risk: 'medium',
      reference: 'Bonne pratique contractuelle',
      page: 19,
    },
    {
      id: 'cp4',
      title: 'Transfert de données hors UE mal encadré',
      description:
        'Absence de mentions SCC / transfert vers des sous-traitants situés hors EEE.',
      risk: 'high',
      reference: 'RGPD art. 46',
      page: 21,
    },
  ],
  summary:
    'Le contrat présente un socle commercial solide, avec quelques déséquilibres sur la responsabilité et la résiliation. Score global favorable sous réserve de négocier les 4 points critiques.',
}

export const agents: AgentDetail[] = [
  {
    id: 'ag1',
    name: 'Analyse juridique',
    initials: 'JU',
    color: '#2563EB',
    status: 'active',
    description:
      'Expertise juridique principale. Analyse la structure du contrat, met en évidence les clauses clés et produit une synthèse argumentée avec les références légales applicables.',
    responsibilities: [
      'Identification des parties et du type de contrat',
      'Mise en évidence des clauses structurantes',
      'Cartographie des obligations réciproques',
      'Rédaction du résumé juridique',
    ],
    inputs: ['Contrat déposé (PDF)', 'Informations du document', 'Contexte du dossier'],
    outputs: ['Résumé structuré', 'Clauses annotées', 'Références légales'],
    stats: {
      analyses: 1284,
      successRate: 97.4,
      avgTime: '1m 42s',
      avgCost: '0,18 $',
    },
  },
  {
    id: 'ag2',
    name: 'Analyse des risques',
    initials: 'RI',
    color: '#F59E0B',
    status: 'active',
    description:
      'Évalue les risques du contrat et classe chaque point par niveau de gravité.',
    responsibilities: [
      'Évaluation du risque global',
      'Détection des déséquilibres',
      'Priorisation des alertes',
    ],
    inputs: ['Clauses identifiées', 'Politique de risque du cabinet'],
    outputs: ['Score de risque', 'Liste des risques', 'Recommandations'],
    stats: {
      analyses: 980,
      successRate: 95.1,
      avgTime: '58s',
      avgCost: '0,09 $',
    },
  },
  {
    id: 'ag3',
    name: 'Analyse de conformité',
    initials: 'CO',
    color: '#22C55E',
    status: 'active',
    description:
      'Vérifie la conformité réglementaire du contrat (RGPD, droit de la consommation, etc.).',
    responsibilities: [
      'Contrôles RGPD',
      'Vérifications sectorielles',
      'Liste des écarts de conformité',
    ],
    inputs: ['Contenu du contrat', 'Référentiels internes'],
    outputs: ['Taux de conformité', 'Écarts constatés', 'Actions correctives'],
    stats: {
      analyses: 742,
      successRate: 96.8,
      avgTime: '1m 05s',
      avgCost: '0,11 $',
    },
  },
]

export const pipelineRun: PipelineRun = {
  id: 'pr1',
  documentName: 'NDA_Partenariat_2026.pdf',
  progress: 62,
  stages: [
    { id: 'p1', label: 'Réception', status: 'done' },
    { id: 'p2', label: 'Lecture du document', status: 'done' },
    { id: 'p3', label: 'Préparation du texte', status: 'done' },
    { id: 'p4', label: 'Analyse du contenu', status: 'done' },
    { id: 'p5', label: 'Classement', status: 'done' },
    { id: 'p6', label: 'Recherche des sources', status: 'active' },
    { id: 'p7', label: 'Sélection des passages', status: 'pending' },
    { id: 'p8', label: 'Expertise', status: 'pending' },
    { id: 'p9', label: 'Synthèse', status: 'pending' },
    { id: 'p10', label: 'Rapport', status: 'pending' },
  ],
  activeStageLabel: 'Recherche des sources',
  activeStageDetail:
    'Recherche des passages du contrat les plus pertinents pour appuyer l’analyse.',
  events: [
    { id: 'e1', time: '12:40:02', message: 'Document reçu et validé', status: 'ok' },
    { id: 'e2', time: '12:40:08', message: 'Lecture du document terminée (8 pages)', status: 'ok' },
    { id: 'e3', time: '12:40:41', message: 'Texte extrait du document numérisé', status: 'ok' },
    { id: 'e4', time: '12:41:05', message: 'Texte préparé pour l’analyse', status: 'ok' },
    { id: 'e5', time: '12:41:33', message: 'Contenu analysé', status: 'ok' },
    { id: 'e6', time: '12:41:48', message: 'Sources internes mises à jour', status: 'ok' },
    { id: 'e7', time: '12:42:01', message: 'Recherche des passages pertinents…', status: 'info' },
  ],
  consumption: {
    pagesAnalyzed: 8,
    sectionsReviewed: 42,
    processingTime: '1m 48s',
    estimatedCost: '0,42 $',
  },
}
