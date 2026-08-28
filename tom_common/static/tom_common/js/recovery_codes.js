/* The recovery-codes page's leave-warning, replacing allauth's mfa/js/recovery_codes.js.
 *
 * Browsers show their own fixed text for beforeunload dialogs (tab close, back button,
 * URL bar) — custom wording there is ignored by every major browser. So: keep beforeunload
 * as the backstop, and intercept in-page link clicks with a dialog that can say WHY it is
 * asking. Clicking the Download button counts as saving the codes and is never intercepted
 * (the template marks it id="download_codes").
 */
(function () {
  const LEAVE_MESSAGE = 'Leave this page without confirming that you have saved your ' +
                        'recovery codes? They will not be shown again.'
  const warn = function (event) { event.preventDefault() }

  document.addEventListener('DOMContentLoaded', function () {
    const saveConfirmation = document.getElementById('codes_saved')
    if (saveConfirmation) {
      window.addEventListener('beforeunload', warn)
      saveConfirmation.addEventListener('change', function () {
        if (this.checked) {
          window.removeEventListener('beforeunload', warn)
        } else {
          window.addEventListener('beforeunload', warn)
        }
      })
      document.addEventListener('click', function (event) {
        if (saveConfirmation.checked) return
        const link = event.target.closest('a[href]')
        if (!link || link.id === 'download_codes' || link.target === '_blank') return
        if (window.confirm(LEAVE_MESSAGE)) {
          window.removeEventListener('beforeunload', warn)  // confirmed once; don't ask again
        } else {
          event.preventDefault()
          event.stopPropagation()
        }
      }, true)
    }

    const textarea = document.getElementById('recovery_codes')
    if (textarea) {
      textarea.addEventListener('click', function (event) {
        event.target.select()
        if (navigator.clipboard) {
          navigator.clipboard.writeText(event.target.value).catch(function () {})
        }
      })
    }
  })
})()
