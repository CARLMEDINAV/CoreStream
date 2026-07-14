declare namespace Cypress {
  interface Chainable {
    login(email: string, password: string): Chainable<void>
    loginAsAdmin(): Chainable<void>
    loginAsDeveloper(): Chainable<void>
    loginAsLeader(): Chainable<void>
    ensureDeveloperHasInProgressTicket(): Chainable<void>
  }
}
