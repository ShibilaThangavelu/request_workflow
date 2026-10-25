# Set up the n8n workflow (n8n Cloud + Slack)

The app sends each request to an n8n workflow. n8n classifies it with Gemini, runs the branch for that type,
posts the team notification to Slack, returns the result to the app and handles the follow-up reminder.
If `N8N_WEBHOOK_URL` is empty, or n8n cannot be reached, the app runs the same logic locally in Python.

## 1. Import the workflow
1. Sign up for an n8n Cloud free trial and open **Workflows**.
2. **Create workflow**, then the three-dots menu, **Import from file**, and choose `n8n/request_workflow.n8n.json`.

## 2. Add the Gemini key
1. **Credentials**, **Create credential**, **Header Auth**.
2. Name: `x-goog-api-key`. Value: your Gemini API key. Save it as `Gemini API key`.
3. Open each node named `Gemini: ...` (6 of them: classify, four draft-reply nodes, draft update) and pick that credential
   if the node shows a credential warning.

## 3. Add Slack
1. At api.slack.com/apps create an app, add the bot scopes `chat:write` and `chat:write.public`, install it to your workspace
   and copy the Bot token (starts with `xoxb-`).
2. In Slack create the channel `#request-workflow` and invite the app (`/invite @your-app`).
3. In n8n: **Credentials**, **Slack API**, access token = the bot token.
4. Open both `Slack: ...` nodes and pick the credential. (To use another channel, change the channel name in those nodes.)

## 4. Add email (Mailtrap sandbox)
Customer replies are emailed through n8n into a Mailtrap test inbox, so nothing reaches a real customer.
1. Sign up at mailtrap.io (free), open **Email Testing**, **Inboxes**, your inbox, then **SMTP Settings** and note the host, port, username and password
   (host `sandbox.smtp.mailtrap.io`, port `2525`).
2. In n8n: **Credentials**, **Create credential**, **SMTP**. Fill in host, port, user and password, leave SSL/TLS off, and save it as `Mailtrap SMTP`.
3. Open the nodes `Email: customer reply` and `Email: approved reply` and pick that credential.
4. Replies that need approval (urgent cases) are only emailed after a person approves them in the app. The app then calls n8n's `/webhook/send-email`
   endpoint, which `Email: approved reply` handles. The app works this URL out from `N8N_WEBHOOK_URL` (or set `N8N_EMAIL_URL`).

## 5. Publish and connect the app
1. Click **Publish** (top right) so the webhooks stay live.
2. Open the `Receive request` node and copy its **Production URL** (it ends in `/webhook/request-workflow`).
3. In the project's `.env` add:
   ```
   N8N_WEBHOOK_URL=<the production URL>
   N8N_REMINDER_MINUTES=1        # optional, for demos: remind after 1 minute instead of the real follow-up time
   ```
4. Restart Streamlit. The sidebar should say **Engine: n8n workflow**, and each result says "Processed by: n8n workflow".

## 6. Check it works
- Submit the example complaint. Slack gets the notification for the Senior Handler, the acknowledgement lands in your Mailtrap inbox, and the app shows the case on every page.
- Submit the urgent example, approve its reply in the app (Approvals page): the email then arrives in Mailtrap.
- In n8n open **Executions** to see the run, branch by branch.
- Mark the case resolved in the app (Follow-ups page): the paused n8n run is resumed and its reminder is cancelled.
- Leave a case open: after the follow-up time n8n posts a reminder to Slack with a draft customer update.

## How the pieces fit
| Part | Where it happens |
| --- | --- |
| Classify type, urgency, confidence | n8n, `Gemini: classify` |
| Validate and pick the branch (below 0.7 confidence goes to human review) | n8n, `Validate and route`, `Which branch` |
| Draft the reply, apply the branch steps, priority and follow-up | n8n, one path per branch |
| Team notification | n8n, Slack |
| Customer emails | n8n sends them through Mailtrap SMTP; the app's Customer inbox mirrors them |
| Approval of urgent replies, case log, dashboard | The Streamlit app |
| Follow-up reminder | n8n Wait node, then Slack. Cancelled when the case is resolved in the app |
