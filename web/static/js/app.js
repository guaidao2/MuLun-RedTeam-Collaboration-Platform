// 幕论红队协同平台 - 全局 JS

// ==================== 语言系统 ====================
const LABELS = {
    zh: {
        asset: '资产', service: '服务', vulnerability: '漏洞',
        credential: '凭据', task: '任务', note: '备注',
        // UI
        login: '登录', logout: '退出', username: '用户名', password: '密码',
        authenticate: '认证', projects: '项目', settings: '设置', rules: '规则',
        new_project: '新建项目', project_name: '项目名称', description: '描述',
        create: '创建', cancel: '取消', save: '保存', add: '添加', delete: '删除',
        edit: '编辑', reload: '重载', submit: '提交', close: '关闭',
        targets: '目标', entries: '条目', analysis: '分析',
        add_target: '添加目标', add_entry: '添加条目',
        ip_address: 'IP 地址', hostname: '主机名', os: '操作系统',
        category: '分类', title: '标题', content: '内容',
        priority: '优先级', status: '状态', author: '作者',
        new_status: '新发现', confirmed: '已确认', exploited: '已利用', fixed: '已修复',
        high: '高', medium: '中', low: '低',
        next_steps: '下一步建议', node_inspector: '节点详情',
        current_user: '当前用户', change_password: '修改密码',
        new_password: '新密码', confirm_password: '确认密码', old_password: '当前密码',
        password_updated: '密码已更新', passwords_mismatch: '两次密码不一致',
        password_too_short: '密码太短', no_projects: '暂无项目，创建一个开始吧',
        no_suggestions: '暂无建议', no_rules: '暂无规则',
        loading: '加载中...', edit_project: '编辑项目',
        confirm_delete_project: '确认删除此项目及所有关联数据?',
        confirm_delete_target: '确认删除此目标?',
        confirm_delete_entry: '确认删除此条目?',
        link_node: '连接此节点', link_mode_hint: '点击图上另一节点创建连线',
        outgoing_links: '发出的连线', confirm_delete_link: '确认删除此连线?',
        import_data: '导入数据', import_type: '导入类型', import_file: '选择文件',
        upload: '上传导入', choose_file: '请选择文件', importing: '导入中...',
        import_failed: '导入失败', target: '目标', advanced: '高级(原始 JSON)', report: '报告',
        privesc: '提权分析', analyze: '分析', members: '成员', add_member: '添加成员',
        auto_layout: '自动排版', refresh: '刷新',
        platform_token: '平台 API Token', token_note: '用于 MCP/外部接口鉴权。初始随机 Token 永久有效，除非手动刷新（旧 Token 立即失效）。',
        copy: '复制', refresh_token: '刷新',
        rules_engine: '规则引擎', trigger_condition: '触发条件',
        suggestion_title: '建议标题', suggestion_reason: '建议原因',
        suggested_tool: '建议工具', select_node: '选择节点查看详情',
        collaborative_platform: '协同渗透测试平台',
        targets_count: '个目标', entries_count: '条记录',
    },
    en: {
        asset: 'ASSET', service: 'SERVICE', vulnerability: 'VULN',
        credential: 'CRED', task: 'TASK', note: 'NOTE',
        login: 'Login', logout: 'Logout', username: 'Username', password: 'Password',
        authenticate: 'Authenticate', projects: 'Projects', settings: 'Settings', rules: 'Rules',
        new_project: 'New Project', project_name: 'Project Name', description: 'Description',
        create: 'Create', cancel: 'Cancel', save: 'Save', add: 'Add', delete: 'Delete',
        edit: 'Edit', reload: 'Reload', submit: 'Submit', close: 'Close',
        targets: 'Targets', entries: 'Entries', analysis: 'Analysis',
        add_target: 'Add Target', add_entry: 'Add Entry',
        ip_address: 'IP Address', hostname: 'Hostname', os: 'OS',
        category: 'Category', title: 'Title', content: 'Content',
        priority: 'Priority', status: 'Status', author: 'Author',
        new_status: 'New', confirmed: 'Confirmed', exploited: 'Exploited', fixed: 'Fixed',
        high: 'high', medium: 'medium', low: 'low',
        next_steps: 'Next Steps', node_inspector: 'Node Inspector',
        current_user: 'Current User', change_password: 'Change Password',
        new_password: 'New Password', confirm_password: 'Confirm Password', old_password: 'Current Password',
        password_updated: 'Password updated', passwords_mismatch: 'Passwords do not match',
        password_too_short: 'Password too short', no_projects: 'No projects. Create one to begin.',
        no_suggestions: 'No suggestions at this time', no_rules: 'No rules defined',
        loading: 'Loading...', edit_project: 'Edit Project',
        confirm_delete_project: 'Delete this project and all related data?',
        confirm_delete_target: 'Delete this target?',
        confirm_delete_entry: 'Delete this entry?',
        link_node: 'Link from here', link_mode_hint: 'Click another node to create a link',
        outgoing_links: 'Outgoing Links', confirm_delete_link: 'Delete this link?',
        import_data: 'Import Data', import_type: 'Import Type', import_file: 'Choose File',
        upload: 'Upload', choose_file: 'Please choose a file', importing: 'Importing...',
        import_failed: 'Import failed', target: 'Target', advanced: 'Advanced (raw JSON)', report: 'Report',
        privesc: 'Privilege Analysis', analyze: 'Analyze', members: 'Members', add_member: 'Add Member',
        auto_layout: 'Auto Layout', refresh: 'Refresh',
        platform_token: 'Platform API Token', token_note: 'For MCP/external auth. The initial random Token is permanent until manually refreshed (old Token invalidated).',
        copy: 'Copy', refresh_token: 'Refresh',
        rules_engine: 'Rules Engine', trigger_condition: 'Trigger Condition',
        suggestion_title: 'Suggestion Title', suggestion_reason: 'Suggestion Reason',
        suggested_tool: 'Suggested Tool', select_node: 'Select a node to view details',
        collaborative_platform: 'Collaborative Pentest Platform',
        targets_count: 'targets', entries_count: 'entries',
    }
};

function getLang() { return localStorage.getItem('lang') || 'zh'; }
function t(key) { return LABELS[getLang()]?.[key] || key; }
function setLang(lang) { localStorage.setItem('lang', lang); location.reload(); }

// ==================== API ====================
async function apiFetch(url, options = {}) {
    const token = localStorage.getItem('token');
    const headers = {'Content-Type': 'application/json', ...options.headers};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const resp = await fetch(url, {...options, headers});
    if (resp.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/';
        return resp;
    }
    return resp;
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    window.location.href = '/';
}

function esc(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    // 进一步转义引号，保证可用于属性上下文（value="..." / onclick 无注入）
    return div.innerHTML
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// 登录状态检查
(function() {
    if (!localStorage.getItem('token') && !window.location.pathname.match(/^\/?$/)) {
        window.location.href = '/';
    }
    const userEl = document.getElementById('current-user');
    if (userEl) userEl.textContent = localStorage.getItem('username') || '';
})();
