const functions = require('firebase-functions');
const admin = require('firebase-admin');
const sgMail = require('@sendgrid/mail');

admin.initializeApp();

sgMail.setApiKey(functions.config().sendgrid.key);

exports.onErrorReport = functions.database
  .ref('/error_reports/{id}')
  .onCreate(async (snap, ctx) => {
    const data = snap.val();
    if (!data) return;

    const blocked = data.blocked ? 'BLOCKED' : 'WARNING';
    const subject = `[SM WoT] ${blocked} ${data.type || 'unknown'} v${data.version || '?'}`;

    const msg = {
      to: 'smwotassistant@gmail.com',
      from: 'noreply@sm-wot-assistant.web.app',
      subject: subject,
      text: JSON.stringify(data, null, 2),
    };

    try {
      await sgMail.send(msg);
    } catch (err) {
      console.error('SendGrid error:', err);
    }
  });
