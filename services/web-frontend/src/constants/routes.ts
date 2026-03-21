/** 路由常量 */
export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  FORBIDDEN: '/forbidden',
  CHAT: '/chat',
  CHAT_SESSION: '/chat/$sessionId',
  APPROVAL: '/approval',
  APPROVAL_DETAIL: '/approval/$id',
  TOOLS: '/tools',
  TOOLS_REGISTER: '/tools/register',
  TOOLS_DETAIL: '/tools/$name',
  AUDIT: '/audit',
  DASHBOARD: '/dashboard',
  USERS: '/users',
  USERS_ROLES: '/users/roles',
  TENANT: '/tenant',
  KNOWLEDGE: '/knowledge',
  KNOWLEDGE_DETAIL: '/knowledge/$docId',
  NOTIFICATIONS: '/notifications',
} as const;

/** 路由路径模板（用于生成路由） */
export const ROUTE_PATHS = {
  chatSession: (sessionId: string) => `/chat/${sessionId}`,
  approvalDetail: (id: string) => `/approval/${id}`,
  toolDetail: (name: string) => `/tools/${name}`,
  knowledgeDetail: (docId: string) => `/knowledge/${docId}`,
} as const;