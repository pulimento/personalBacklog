import Foundation
import FoundationModels

struct AssistantInput: Decodable {
    let request: String
    let currentRelease: String?
    let releases: [String]
    let existingTitles: [String]
}

@Generable
struct GeneratedTask {
    @Guide(description: "A concise, imperative, single-line task title.")
    var title: String

    @Guide(description: "One of the available release strings, or the literal word none when unassigned.")
    var release: String

    @Guide(description: "A priority from 1 (highest) through 5 (parked).")
    var priority: Int

    @Guide(description: "Exactly one of S, M, or L. S is isolated work, M is related work in one layer, and L is cross-cutting work.")
    var size: String

    @Guide(description: "A useful Markdown task body with Context, Desired outcome, Decisions and constraints, and Acceptance criteria headings.")
    var body: String
}

struct Output: Encodable {
    let title: String
    let release: String
    let priority: Int
    let size: String
    let body: String
}

@main
struct BacklogAppleIntelligence {
    static func main() async {
        do {
            let inputData = FileHandle.standardInput.readDataToEndOfFile()
            let input = try JSONDecoder().decode(AssistantInput.self, from: inputData)
            let model = SystemLanguageModel.default
            guard case .available = model.availability else {
                throw NSError(domain: "PersonalBacklog", code: 1, userInfo: [
                    NSLocalizedDescriptionKey: "Apple Intelligence is unavailable on this Mac. Enable it and wait for the on-device model to finish downloading."
                ])
            }
            let releaseList = input.releases.isEmpty ? "none" : input.releases.joined(separator: ", ")
            let currentRelease = input.currentRelease ?? "none"
            let knownTasks = input.existingTitles.prefix(60).joined(separator: " | ")
            let instructions = """
            You turn a person's natural-language request into exactly one Personal Backlog task.
            Generate a proposal only; never claim that you created, changed, or completed a task.
            Use priority 1 for top priority. Choose a release from the supplied available releases; use none only when the request does not relate to a release.
            The body must be concise Markdown. Do not include secrets, credentials, or personal data.
            """
            let prompt = """
            Person's request:
            \(input.request)

            Current release: \(currentRelease)
            Available releases: \(releaseList)
            Existing task titles, for avoiding duplicates: \(knownTasks)
            """
            let session = LanguageModelSession(model: model, instructions: instructions)
            let response = try await session.respond(to: prompt, generating: GeneratedTask.self)
            let proposal = response.content
            let output = Output(
                title: proposal.title,
                release: proposal.release,
                priority: proposal.priority,
                size: proposal.size,
                body: proposal.body
            )
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            print(String(data: try encoder.encode(output), encoding: .utf8)!)
        } catch {
            FileHandle.standardError.write(Data("Apple Intelligence provider error: \(error.localizedDescription)\n".utf8))
            exit(2)
        }
    }
}
