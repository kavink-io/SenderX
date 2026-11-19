const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ARTIFACT_DIR = path.resolve('C:\\Users\\Kavin\\.gemini\\antigravity\\brain\\5eb16911-a235-49ba-b31c-9acf2abed835');
const TEMP_PROFILE = path.join(process.env.TEMP || 'C:\\temp', 'chrome_cdp_parta_' + Date.now());
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9230;

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getJson(url) {
    return new Promise((resolve, reject) => {
        http.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch(e) {
                    reject(e);
                }
            });
        }).on('error', reject);
    });
}

class CDPClient {
    constructor(wsUrl) {
        this.ws = new WebSocket(wsUrl);
        this.id = 0;
        this.callbacks = new Map();
        
        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.id && this.callbacks.has(msg.id)) {
                const cb = this.callbacks.get(msg.id);
                this.callbacks.delete(msg.id);
                if (msg.error) {
                    cb.reject(new Error(JSON.stringify(msg.error)));
                } else {
                    cb.resolve(msg.result);
                }
            }
        };
    }

    ready() {
        return new Promise((resolve, reject) => {
            if (this.ws.readyState === WebSocket.OPEN) return resolve();
            this.ws.onopen = () => resolve();
            this.ws.onerror = (err) => reject(err);
        });
    }

    send(method, params = {}) {
        return new Promise((resolve, reject) => {
            const reqId = ++this.id;
            this.callbacks.set(reqId, { resolve, reject });
            this.ws.send(JSON.stringify({ id: reqId, method, params }));
        });
    }

    async evaluate(expression) {
        const res = await this.send('Runtime.evaluate', {
            expression,
            returnByValue: true,
            awaitPromise: true
        });
        if (res.exceptionDetails) {
            throw new Error(JSON.stringify(res.exceptionDetails));
        }
        return res.result ? res.result.value : undefined;
    }

    async captureScreenshot(filename) {
        const res = await this.send('Page.captureScreenshot', { format: 'png' });
        const filePath = path.join(ARTIFACT_DIR, filename);
        fs.writeFileSync(filePath, Buffer.from(res.data, 'base64'));
        console.log(`Saved screenshot: ${filePath} (${res.data.length} bytes base64)`);
    }

    close() {
        try { this.ws.close(); } catch(e) {}
    }
}

async function main() {
    console.log(`1. Launching Chrome with CDP on port ${PORT}...`);
    const chrome = spawn(CHROME_PATH, [
        `--remote-debugging-port=${PORT}`,
        `--user-data-dir=${TEMP_PROFILE}`,
        '--headless=new',
        '--disable-gpu',
        '--no-first-run',
        '--no-default-browser-check',
        'about:blank'
    ]);

    let cdpClient = null;

    try {
        let connected = false;
        let targets = null;
        for (let i = 0; i < 20; i++) {
            await sleep(400);
            try {
                targets = await getJson(`http://127.0.0.1:${PORT}/json`);
                if (targets && targets.length > 0) {
                    connected = true;
                    break;
                }
            } catch(e) {}
        }

        if (!connected) throw new Error("Could not connect to Chrome CDP");

        const pageTarget = targets.find(t => t.type === 'page');
        cdpClient = new CDPClient(pageTarget.webSocketDebuggerUrl);
        await cdpClient.ready();

        await cdpClient.send('Page.enable');
        await cdpClient.send('DOM.enable');
        await cdpClient.send('Runtime.enable');
        await cdpClient.send('Emulation.setDeviceMetricsOverride', {
            width: 1440,
            height: 900,
            deviceScaleFactor: 1,
            mobile: false
        });

        console.log("2. Navigating to http://localhost:5000/ ...");
        await cdpClient.send('Page.navigate', { url: 'http://localhost:5000/' });
        await sleep(1500);

        // Login as Super Admin first to make sure Acme org exists, or login as Org Admin directly
        console.log("3. Logging in as Super Admin to access Platform...");
        await cdpClient.evaluate(`
            document.getElementById('login-email').value = 'senderx@id.com';
            document.getElementById('login-password').value = 'SenderX@Root2026!';
            document.getElementById('btn-login').click();
        `);
        for (let i = 0; i < 30; i++) {
            await sleep(500);
            const inApp = await cdpClient.evaluate(`document.getElementById('app-shell')?.classList.contains('active')`);
            if (inApp) break;
        }
        await sleep(1500);

        console.log("4. Capturing Platform Admin Dashboard (confirming no stray Close button)...");
        await cdpClient.captureScreenshot('task5_4_platform_admin_verified.png');

        // Logout
        console.log("5. Logging out Super Admin...");
        await cdpClient.evaluate(`document.getElementById('btn-header-logout')?.click()`);
        await sleep(1500);

        // Login as Org Admin: senderx.test.admin@example.com (or reset password if needed)
        console.log("6. Logging in as Org Admin...");
        // Let's create an org admin with known credentials in Mongo if needed, or login directly
        const orgAdminLogin = await cdpClient.evaluate(`
            (async () => {
                const res = await ApiClient.login('admin-a-6411df@acme.com', 'AdminPass123!456');
                return res;
            })()
        `);
        console.log("Org admin login result:", orgAdminLogin);
        if (!orgAdminLogin || !orgAdminLogin.success) {
            console.log("Using API to create test org & admin for UI verification...");
            // Log in as Super Admin again to create a clean org
            await cdpClient.evaluate(`
                (async () => {
                    await ApiClient.login('senderx@id.com', 'SenderX@Root2026!');
                    const orgRes = await ApiClient.createOrganization({
                        name: 'Verified Acme Corp',
                        slug: 'verified-acme-' + Date.now(),
                        admin_name: 'Acme Admin',
                        admin_email: 'admin.acme@verified.io',
                        admin_password: 'Password123!456',
                        employee_code: 'ADM-100'
                    });
                    return orgRes;
                })()
            `);
            await sleep(1000);
            await cdpClient.evaluate(`
                ApiClient.login('admin.acme@verified.io', 'Password123!456');
            `);
            await sleep(2000);
        } else {
            await sleep(1500);
        }

        // Navigate to Employees tab
        console.log("7. Navigating to Employees & Roles...");
        await cdpClient.evaluate(`
            switchTab('tab-org-users');
            loadOrgUsers();
        `);
        await sleep(2000);

        // Open Add Employee Modal
        console.log("8. Opening Add Employee Modal...");
        await cdpClient.evaluate(`openModal('modal-create-user')`);
        await sleep(1000);
        await cdpClient.captureScreenshot('task5_4_add_employee_modal_dept_phone.png');

        // Fill in employee with Department and Phone
        console.log("9. Creating employee with Department & Phone...");
        await cdpClient.evaluate(`
            document.getElementById('new-user-name').value = 'Robert Vance';
            document.getElementById('new-user-email').value = 'robert.vance@verified.io';
            document.getElementById('new-user-employee-code').value = 'EMP-909';
            document.getElementById('new-user-department').value = 'Refrigeration & Logistics';
            document.getElementById('new-user-phone').value = '+1 212 555 0144';
            document.getElementById('new-user-password').value = 'SecurePass123!456';
        `);
        await sleep(500);
        await cdpClient.captureScreenshot('task5_4_add_employee_filled.png');

        await cdpClient.evaluate(`
            document.getElementById('form-create-user').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        `);
        await sleep(2500);

        // View Employee Details
        console.log("10. Viewing Employee Details Modal...");
        await cdpClient.evaluate(`
            (() => {
                const row = Array.from(document.querySelectorAll('#users-table-body tr')).find(tr => tr.innerText.includes('Robert Vance'));
                if (row) {
                    const btn = row.querySelector('button');
                    if (btn) btn.click();
                }
            })()
        `);
        await sleep(1500);
        await cdpClient.captureScreenshot('task5_4_employee_details_rich.png');

        // Close details modal
        await cdpClient.evaluate(`closeModal('modal-user-details')`);
        await sleep(500);

        // Open Delete Employee Modal
        console.log("11. Opening Rich Employee Deletion Modal...");
        await cdpClient.evaluate(`
            (() => {
                const delRow = Array.from(document.querySelectorAll('#users-table-body tr')).find(tr => tr.innerText.includes('Robert Vance'));
                if (delRow) {
                    const delBtn = delRow.querySelector('.btn-danger');
                    if (delBtn) delBtn.click();
                }
            })()
        `);
        await sleep(1500);
        await cdpClient.captureScreenshot('task5_4_employee_deletion_rich_dialog.png');

        console.log("Verification finished successfully!");

    } catch(err) {
        console.error("Verification failed:", err);
    } finally {
        if (cdpClient) cdpClient.close();
        chrome.kill();
        try {
            fs.rmSync(TEMP_PROFILE, { recursive: true, force: true });
        } catch(e) {}
    }
}

main();
