// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ElectionContract {
    struct Vote {
        uint256 electionId;
        uint256 candidateId;
        address voter;
    }

    mapping(uint256 => mapping(address => bool)) public hasVoted;  // electionId => voter => hasVoted
    mapping(uint256 => mapping(uint256 => uint256)) public voteCounts;  // electionId => candidateId => voteCount
    
    event VoteCast(uint256 electionId, uint256 candidateId, address voter);

    function castVote(uint256 _electionId, uint256 _candidateId) public {
        require(!hasVoted[_electionId][msg.sender], "Already voted in this election");
        
        hasVoted[_electionId][msg.sender] = true;
        voteCounts[_electionId][_candidateId]++;
        
        emit VoteCast(_electionId, _candidateId, msg.sender);
    }

    function getVoteCount(uint256 _electionId, uint256 _candidateId) public view returns (uint256) {
        return voteCounts[_electionId][_candidateId];
    }

    function checkVoted(uint256 _electionId, address _voter) public view returns (bool) {
        return hasVoted[_electionId][_voter];
    }
}
