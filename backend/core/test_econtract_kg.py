import unittest
import networkx as nx
from backend.core import econtract_kg

class TestEContractKG(unittest.TestCase):
    def setUp(self):
        # Example contract text with multiple entities and business logic
        self.contract_text = """
        This Rental Agreement is made between Alice (the Landlord) and Bob (the Tenant) for the property at 123 Main St. The rent is $1000 per month, payable on the 1st of each month. The agreement starts on 2023-01-01 and ends on 2023-12-31. Bob must pay a security deposit of $2000. If rent is not paid by the 5th, a late fee of $50 applies.
        """

    def test_entity_preservation(self):
        G = econtract_kg.build_econtract_knowledge_graph(self.contract_text)
        entities = [d['label'] for n, d in G.nodes(data=True)]
        # Ensure key entities are preserved
        self.assertIn('Alice', entities)
        self.assertIn('Bob', entities)
        self.assertIn('123 Main St', entities)
        self.assertIn('$1000', entities)
        self.assertIn('2023-01-01', entities)
        self.assertIn('2023-12-31', entities)

    def test_business_logic(self):
        G = econtract_kg.build_econtract_knowledge_graph(self.contract_text)
        # Check for correct relationships (edges) between entities
        edge_labels = [(G.nodes[u]['label'], G.nodes[v]['label'], d.get('label')) for u, v, d in G.edges(data=True)]
        # Example: Bob pays rent to Alice
        self.assertTrue(any('Bob' in e and 'Alice' in e and 'pays' in (l or '') for e, l in zip(edge_labels, [d[2] for d in edge_labels])))
        # Example: Security deposit obligation
        self.assertTrue(any('Bob' in e and '$2000' in e for e in edge_labels))

    def test_entity_coverage(self):
        G = econtract_kg.build_econtract_knowledge_graph(self.contract_text)
        # Check that all expected entity types are present
        types = set(d.get('type') for n, d in G.nodes(data=True))
        self.assertIn('Person', types)
        self.assertIn('Money', types)
        self.assertIn('Date', types)
        self.assertIn('Location', types)

    def test_failing_case_missing_entity(self):
        # Text missing a required entity (e.g., no tenant)
        text = "This Rental Agreement is made for the property at 123 Main St. The rent is $1000 per month."
        G = econtract_kg.build_econtract_knowledge_graph(text)
        entities = [d['label'] for n, d in G.nodes(data=True)]
        # Should fail: no tenant entity
        self.assertNotIn('Tenant', entities)

    def test_failing_case_incorrect_logic(self):
        # Text with ambiguous payment (no payer specified)
        text = "A payment of $500 is required."
        G = econtract_kg.build_econtract_knowledge_graph(text)
        edge_labels = [(G.nodes[u]['label'], G.nodes[v]['label'], d.get('label')) for u, v, d in G.edges(data=True)]
        # Should fail: no edge from a person to payment
        self.assertFalse(any('Person' in G.nodes[u].get('type', '') and 'Money' in G.nodes[v].get('type', '') for u, v, d in G.edges(data=True)))

if __name__ == '__main__':
    unittest.main()
