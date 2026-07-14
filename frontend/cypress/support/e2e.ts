// Comandos custom para CoreStream E2E
// Credenciales de prueba según plan de desarrollo CS-046

Cypress.Commands.add('login', (email: string, password: string) => {
  cy.visit('/#/login')
  cy.intercept('POST', '**/api/auth/login').as('loginRequest')
  cy.get('input[type="email"]', { timeout: 10000 }).should('be.visible').type(email)
  cy.get('input[type="password"]').type(password)
  cy.get('button[type="submit"]').click()
  cy.wait('@loginRequest').its('response.statusCode').should('eq', 200)
  cy.url({ timeout: 10000 }).should('not.match', /#\/login$/)
})

Cypress.Commands.add('loginAsAdmin', () => {
  cy.login('admin@example.com', 'Admin@123!')
})

Cypress.Commands.add('loginAsDeveloper', () => {
  cy.login('userdev@example.com', 'Jjgg11@!')
})

Cypress.Commands.add('loginAsLeader', () => {
  cy.login('leader@example.com', 'Leader@123!')
})

/**
 * Crea un ticket de prueba asignado al developer y lo inicia (IN_PROGRESS).
 * Requiere que exista al menos una aplicación con una épica.
 * Usa la API directamente para evitar dependencia de la UI.
 */
Cypress.Commands.add('ensureDeveloperHasInProgressTicket', () => {
  // 1. Login como admin para obtener token
  cy.request({
    method: 'POST',
    url: '/api/auth/login',
    body: { email: 'admin@example.com', password: 'Admin@123!' },
  }).then(function(loginResp) {
    const adminToken = loginResp.body.access_token
    const headers = { Authorization: 'Bearer ' + adminToken }

    // 2. Obtener usuario developer
    cy.request({ method: 'GET', url: '/api/users/', headers: headers }).then(function(usersResp) {
      const rawUsers = usersResp.body
      const users = Array.isArray(rawUsers) ? rawUsers : (rawUsers.items || [])
      const dev = users.find(function(u) { return u.email === 'userdev@example.com' })
      if (!dev) return

      // 3. Obtener primera aplicación disponible
      cy.request({ method: 'GET', url: '/api/applications/', headers: headers }).then(function(appsResp) {
        const rawApps = appsResp.body
        const apps = Array.isArray(rawApps) ? rawApps : (rawApps.items || rawApps.data || [])
        if (!apps.length) return

        const appId = apps[0].id

        // 4. Obtener épicas de la aplicación
        cy.request({ method: 'GET', url: '/api/epics/by-app/' + appId, headers: headers }).then(function(epicsResp) {
          const epics = Array.isArray(epicsResp.body) ? epicsResp.body : []
          if (!epics.length) return

          const epicId = epics[0].id

          // 5. Crear ticket asignado al developer
          cy.request({
            method: 'POST',
            url: '/api/tickets/',
            headers: headers,
            body: {
              title: 'Ticket Dev E2E',
              description: 'Test ticket para E2E',
              epic_id: epicId,
              assignee_id: dev.id,
              priority: 'MEDIUM',
            },
          }).then(function(ticketResp) {
            const ticketId = ticketResp.body.id

            // 6. Iniciar el ticket (IN_PROGRESS)
            cy.request({
              method: 'POST',
              url: '/api/tickets/' + ticketId + '/start',
              headers: headers,
            })
          })
        })
      })
    })
  })
})
